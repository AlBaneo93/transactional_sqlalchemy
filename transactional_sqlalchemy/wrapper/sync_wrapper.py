from __future__ import annotations

import functools
import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.session import SessionTransaction

from transactional_sqlalchemy import SessionHandler
from transactional_sqlalchemy.enums import Propagation
from transactional_sqlalchemy.utils.transaction_util import (
    add_session_to_context,
    get_session_from_context,
    remove_session_from_context,
)
from transactional_sqlalchemy.wrapper.common import (
    __check_is_commit,
    __get_safe_kwargs,
    get_current_session_objects,
    reset_savepoint_objects,
)


def _do_fn_with_tx(
    func,
    sess_: Session,
    *args,
    read_only: bool = False,
    is_session_owner: bool = False,  # 세션 소유권 명시
    auto_flush: bool = True,  # 새로운 옵션
    **kwargs,
):
    sess_.get_transaction()
    if sess_.get_transaction() is None:
        # 트랜잭션 명시적 시작
        sess_.begin()

    add_session_to_context(sess_)
    object_snapshots: set = get_current_session_objects(sess_)

    kwargs, no_rollback_for, rollback_for = __get_safe_kwargs(kwargs)

    origin_autoflush = sess_.autoflush
    if read_only:
        sess_.autoflush = False

    try:
        result: Any = None

        try:
            kwargs["session"] = sess_
            result = func(*args, **kwargs)

            # 세션 소유자만 커밋 수행
            if is_session_owner and not read_only and sess_.is_active:
                sess_.commit()
            elif not is_session_owner and sess_.is_active and auto_flush:
                if sess_.dirty or sess_.new or sess_.deleted:
                    sess_.flush()
        except Exception as e:
            if not __check_is_commit(e, rollback_for, no_rollback_for):
                raise

        return result
    except Exception:
        logging.exception("Transaction error occurred")
        # 객체 상태 복원
        reset_savepoint_objects(sess_, object_snapshots)

        # 세션 소유자이거나 트랜잭션이 활성 상태라면 롤백
        if sess_.is_active:
            sess_.rollback()

        raise
    finally:
        sess_.autoflush = origin_autoflush  # autoflush 복원

        # 세션 정리
        if is_session_owner:
            sess_.close()

        # 컨텍스트에서 세션 제거
        remove_session_from_context()


def __sync_transaction_wrapper(
    func, propagation: Propagation, rollback_for: tuple[type[Exception]], no_rollback_for: tuple[type[Exception, ...]]
):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        handler = SessionHandler()

        current_session: Session | None = None
        try:
            current_session: Session = get_session_from_context()
        except ValueError:
            # 스택이 비어있음 새로운 트랜잭션 시작
            pass

        kwargs["__rollback_for__"] = rollback_for
        kwargs["__no_rollback_for__"] = no_rollback_for

        # if current_session is None:
        #     current_session, scoped_ = handler.get_manager().get_new_session()

        if propagation == Propagation.REQUIRES:
            if current_session is not None:
                # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                return _do_fn_with_tx(
                    func,
                    current_session,
                    is_session_owner=False,  # 부모가 세션 관리
                    auto_flush=True,
                    *args,
                    **kwargs,
                )
            else:
                # 사용 중인 트랜잭션이 없는경우, 새로운 트랜잭션 사용
                new_session, scoped_ = handler.get_manager().get_new_session()

                try:
                    return _do_fn_with_tx(
                        func,
                        new_session,
                        is_session_owner=True,  # 새로운 세션 소유권 있음
                        auto_flush=False,
                        *args,
                        **kwargs,
                    )
                finally:
                    if scoped_ is not None:
                        scoped_.remove()

        elif propagation == Propagation.REQUIRES_NEW:
            new_session, new_scoped_ = handler.get_manager().get_new_session(force=True)  # 강제로 세션 생성 + 시작
            try:
                return _do_fn_with_tx(func, new_session, is_session_owner=True, auto_flush=False, *args, **kwargs)
            finally:
                if new_scoped_ is not None:
                    new_scoped_.remove()

        elif propagation == Propagation.NESTED:
            if current_session is None:
                raise ValueError("NESTED propagation requires an existing transaction")

            current_objects: set = get_current_session_objects(current_session)

            # 사용중인 세션이 있다면 해당 세션을 사용
            save_point: SessionTransaction = current_session.begin_nested()

            try:
                kwargs, _, _ = __get_safe_kwargs(kwargs)

                kwargs["session"] = current_session
                result = func(*args, **kwargs)

                current_session.flush()
                return result
            except Exception:
                reset_savepoint_objects(current_session, current_objects)
                # 오류 발생 시, save point만 롤백
                if save_point.is_active:
                    save_point.rollback()
                raise
        else:
            raise ValueError(f"Unsupported propagation type: {propagation}")

    return wrapper
