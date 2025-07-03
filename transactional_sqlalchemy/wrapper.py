import functools
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.orm import Session
from sqlalchemy.orm.scoping import scoped_session

from transactional_sqlalchemy import SessionHandler, scoped_session_context, transaction_context
from transactional_sqlalchemy.enums import Propagation


def __check_is_commit(
    exc: Exception, rollback_for: tuple[type[Exception]], no_rollback_for: tuple[type[Exception], ...]
):
    if any(isinstance(exc, exc_type) for exc_type in no_rollback_for):
        # 롤백 대상이 아닌 경우 commit
        return True

    elif any(isinstance(exc, exc_type) for exc_type in rollback_for):
        # 롤백 대상 예외인 경우 롤백
        return False

    return False


async def _a_do_fn_with_tx(
    func,
    sess_: AsyncSession,
    *args,
    **kwargs,
):
    transaction_context.set(sess_)

    result = None

    kwargs, no_rollback_for, rollback_for = __get_safe_kwargs(kwargs)

    try:
        kwargs["session"] = sess_
        result = await func(*args, **kwargs)
        if sess_.is_active:
            # 트랜잭션이 활성화 되어 있다면 커밋
            await sess_.commit()

    except Exception as e:
        logging.exception("")

        if __check_is_commit(e, rollback_for, no_rollback_for):
            # 롤백 대상이 아닌 경우 commit
            if sess_.is_active:
                result = await sess_.commit()

        else:
            # 롤백 대상 예외인 경우 롤백
            if sess_.is_active:
                await sess_.rollback()
            raise

    finally:
        transaction_context.set(None)

    return result


def _do_fn_with_tx(
    func,
    sess_: Session,
    *args,
    **kwargs,
):
    tx = sess_.get_transaction()
    if sess_.get_transaction() is None:
        # 트랜잭션 명시적 시작
        tx = sess_.begin()

    transaction_context.set(sess_)

    result = None

    kwargs, no_rollback_for, rollback_for = __get_safe_kwargs(kwargs)

    try:
        kwargs["session"] = sess_
        result = func(*args, **kwargs)
        if tx.is_active:
            tx.commit()

    except Exception as e:
        logging.exception("")

        if __check_is_commit(e, rollback_for, no_rollback_for):
            # 롤백 대상이 아닌 경우 commit
            if tx.is_active:
                tx.commit()

        else:
            # 롤백 대상 예외인 경우 롤백
            if tx.is_active:
                tx.rollback()
            raise
    finally:
        # sess_.close()
        transaction_context.set(None)

    return result


def __get_safe_kwargs(kwargs):
    rollback_for: tuple[type[Exception]] = kwargs.get("__rollback_for__", (Exception,))
    no_rollback_for: tuple[type[Exception], ...] = kwargs.get("__no_rollback_for__", ())
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}

    return kwargs, no_rollback_for, rollback_for


def __sync_transaction_wrapper(
    func, propagation: Propagation, rollback_for: tuple[type[Exception]], no_rollback_for: tuple[type[Exception, ...]]
):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        current_session: Session = transaction_context.get()
        scoped_: scoped_session | None = scoped_session_context.get()

        handler = SessionHandler()

        kwargs["__rollback_for__"] = rollback_for
        kwargs["__no_rollback_for__"] = no_rollback_for

        if current_session is None:
            current_session, scoped_ = handler.get_manager().get_new_session()

        if propagation == Propagation.REQUIRES:
            if current_session:
                # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                using_session = current_session
            else:
                # 사용 중인 트랜잭션이 없는경우, 새로운 트랜잭션 사용
                sess_, sc_ = handler.get_manager().get_new_session()
                using_session = sess_
                scoped_ = sc_

            result = _do_fn_with_tx(
                func,
                using_session,
                *args,
                **kwargs,
            )
            if using_session.is_active:
                using_session.close()
            if scoped_ is not None:
                scoped_.remove()
            return result

        elif propagation == Propagation.REQUIRES_NEW:
            new_session, new_scoped_ = handler.get_manager().get_new_session(True)  # 강제로 세션 생성 + 시작

            result = _do_fn_with_tx(func, new_session, *args, **kwargs)

            if new_session.is_active:
                new_session.close()
                new_scoped_.remove()

            # 기존 세션으로 복구
            transaction_context.set(current_session)

            return result

        elif propagation == Propagation.NESTED:
            # 사용중인 세션이 있다면 해당 세션을 사용
            save_point = current_session.begin_nested()
            kwargs, _, _ = __get_safe_kwargs(kwargs)

            try:
                kwargs["session"] = current_session
                result = func(*args, **kwargs)
                current_session.flush()
                return result
            except Exception:
                # 오류 발생 시, save point만 롤백
                if save_point.is_active:
                    save_point.rollback()
                raise

    return wrapper


def __async_transaction_wrapper(
    func, propagation: Propagation, rollback_for: tuple[type[Exception]], no_rollback_for: tuple[type[Exception, ...]]
):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        current_session: AsyncSession = transaction_context.get()
        scoped_: async_scoped_session | None = scoped_session_context.get()
        handler = SessionHandler()

        if current_session is None:
            current_session, scoped_ = handler.get_manager().get_new_async_session()

        kwargs["__rollback_for__"] = rollback_for
        kwargs["__no_rollback_for__"] = no_rollback_for

        if propagation == Propagation.REQUIRES:
            if current_session:
                # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                using_session = current_session

            else:
                # 사용 중인 트랜잭션이 없는경우, 새로운 트랜잭션 사용
                sess_, scoped_ = handler.get_manager().get_new_async_session()
                using_session = sess_

            result = await _a_do_fn_with_tx(
                func,
                using_session,
                *args,
                **kwargs,
            )
            await using_session.close()
            if scoped_ is not None:
                await scoped_.remove()  # 세션 제거
            return result

        elif propagation == Propagation.REQUIRES_NEW:
            new_session, scoped_ = handler.get_manager().get_new_session(True)  # 강제로 세션 생성

            result = await _a_do_fn_with_tx(func, new_session, *args, **kwargs)
            await new_session.close()
            # 기존 세션으로 복구
            transaction_context.set(current_session)
            scoped_session_context.set(scoped_)
            return result

        elif propagation == Propagation.NESTED:
            # 사용중인 세션이 있다면 해당 세션을 사용
            save_point = await current_session.begin_nested()
            kwargs, _, _ = __get_safe_kwargs(kwargs)
            try:
                kwargs["session"] = current_session
                result = await func(*args, **kwargs)
                await current_session.flush()
                return result
            except Exception:
                # 오류 발생 시, save point만 롤백
                if save_point.is_active:
                    await save_point.rollback()
                raise

    return async_wrapper
