from __future__ import annotations

import functools
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.session import AsyncSessionTransaction

from transactional_sqlalchemy.config import SessionHandler
from transactional_sqlalchemy.enums import Propagation
from transactional_sqlalchemy.utils.transaction_util import (
    add_session_to_context,
    get_session_from_context,
    remove_session_from_context,
)
from transactional_sqlalchemy.wrapper.common import (
    __check_is_commit,
    __get_safe_kwargs,
    a_get_current_session_objects,
    has_pending_changes,
    reset_savepoint_objects,
)


async def _a_do_fn_with_tx(
    func,
    sess_: AsyncSession,
    *args,
    read_only: bool = False,
    is_session_owner: bool = False,  # 세션 소유권 명시
    auto_flush: bool = True,  # 새로운 옵션
    **kwargs,
):
    add_session_to_context(sess_)

    object_snapshots: set = a_get_current_session_objects(sess_)

    kwargs, no_rollback_for, rollback_for = __get_safe_kwargs(kwargs)

    origin_autoflush = sess_.autoflush
    if read_only:
        sess_.autoflush = False  # autoflush 비활성화
        # DB에 따라 읽기 전용 트랜잭션 설정 (예: PostgreSQL)
        # await sess_.execute(text("SET TRANSACTION READ ONLY"))

    try:
        result: Any = None
        try:
            kwargs["session"] = sess_
            result = await func(*args, **kwargs)

            if is_session_owner and not read_only and sess_.is_active:
                await sess_.commit()
            elif not is_session_owner and sess_.is_active and auto_flush:
                if sess_.dirty or sess_.new or sess_.deleted:
                    await sess_.flush()
        except Exception as e:
            if not __check_is_commit(e, rollback_for, no_rollback_for):
                raise

        return result
    except Exception:
        logging.exception("Transaction error occurred")

        reset_savepoint_objects(sess_, object_snapshots)
        # 예외 발생 시, 롤백 처리
        if sess_.is_active:
            await sess_.rollback()
        raise

    finally:
        sess_.autoflush = origin_autoflush  # autoflush 복원
        if is_session_owner:
            await sess_.close()
        # 컨텍스트에서 세션 제거
        remove_session_from_context()


def __async_transaction_wrapper(
    func,
    propagation: Propagation,
    read_only: bool,
    rollback_for: tuple[type[Exception]],
    no_rollback_for: tuple[type[Exception, ...]],
):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        handler = SessionHandler()

        current_session: AsyncSession | None = None
        try:
            current_session: AsyncSession = get_session_from_context()
        except ValueError:
            # 스택이 비어있음 새로운 트랜잭션 시작
            pass

        kwargs["__rollback_for__"] = rollback_for
        kwargs["__no_rollback_for__"] = no_rollback_for

        if propagation == Propagation.REQUIRES:
            if current_session is not None:
                # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                return await _a_do_fn_with_tx(
                    func,
                    current_session,
                    is_session_owner=False,  # 부모가 세션 관리
                    auto_flush=True,
                    read_only=read_only,
                    *args,
                    **kwargs,
                )

            else:
                # 새로운 트랜잭션 생성 - 세션 소유권 있음
                new_session, scoped_ = handler.get_manager().get_new_async_session()

                try:
                    result = await _a_do_fn_with_tx(
                        func,
                        new_session,
                        is_session_owner=True,  # 현재 함수가 세션 관리
                        auto_flush=False,
                        read_only=read_only,
                        *args,
                        **kwargs,
                    )
                    return result
                finally:
                    # scoped session 정리
                    if scoped_ is not None:
                        await scoped_.remove()

        elif propagation == Propagation.REQUIRES_NEW:
            new_session, scoped_ = handler.get_manager().get_new_async_session(force=True)
            try:
                return await _a_do_fn_with_tx(
                    func, new_session, is_session_owner=True, auto_flush=False, read_only=read_only, *args, **kwargs
                )
            finally:
                if scoped_ is not None:
                    await scoped_.remove()

        elif propagation == Propagation.NESTED:
            if current_session is None:
                raise ValueError("NESTED propagation requires an existing transaction")

            # 중첩 트랜잭션 (savepoint) 생성
            save_point: AsyncSessionTransaction = await current_session.begin_nested()
            object_snapshots: set = a_get_current_session_objects(save_point)

            try:
                kwargs, _, _ = __get_safe_kwargs(kwargs)
                kwargs["session"] = current_session
                result: Any = await func(*args, **kwargs)

                if not read_only and has_pending_changes(current_session):
                    await current_session.flush()  # 중첩 트랜잭션에서 변경 사항을 즉시 반영

                return result

            except Exception as e:
                if save_point.is_active and not __check_is_commit(e, rollback_for, no_rollback_for):
                    reset_savepoint_objects(save_point.session, object_snapshots)
                    await save_point.rollback()

                raise
            finally:
                # 중첩 트랜잭션 종료
                if save_point.is_active:
                    if read_only:
                        await save_point.rollback()
                    else:
                        # ReadOnly 트랜잭션이 아니면서, 성공 시 commit (RELEASE SAVEPOINT)
                        await save_point.commit()

    return async_wrapper
