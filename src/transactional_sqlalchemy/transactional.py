import functools
import logging
from collections.abc import Awaitable
from enum import Enum
from inspect import iscoroutinefunction, unwrap
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction
from sqlalchemy.orm import Session, SessionTransaction

from transactional_sqlalchemy import SessionHandler, transaction_context

AsyncCallable = Callable[..., Awaitable]


class Propagation(Enum):
    REQUIRES = 'REQUIRES'
    REQUIRES_NEW = 'REQUIRES_NEW'
    NESTED = 'NESTED'


async def _a_do_fn_with_tx(func, sess_: AsyncSession, *args, **kwargs):
    tx: AsyncSessionTransaction = await sess_.begin()  # 트랜잭션 명시적 시작
    transaction_context.set(sess_)

    try:
        kwargs['session'] = sess_
        result = await func(*args, **kwargs)
        if tx.is_active:
            # 트랜잭션이 활성화 되어 있다면 커밋
            await tx.commit()
        return result
    except:
        logging.exception('')
        if tx.is_active:
            await tx.rollback()
        raise
    finally:
        await sess_.aclose()
        transaction_context.set(None)


def _do_fn_with_tx(func, sess_: Session, *args, **kwargs):
    tx: SessionTransaction = sess_.get_transaction()  # 시작 되어 넘어옴

    if tx is None:
        tx = sess_.begin() # 트랜잭션 명시적 시작
    transaction_context.set(sess_)

    try:
        kwargs['session'] = sess_
        result = func(*args, **kwargs)
        if tx.is_active:
            tx.commit()
        return result
    except:
        logging.exception('')
        if tx.is_active:
            tx.rollback()
        raise
    finally:
        sess_.close()
        transaction_context.set(None)


def transactional(
    _func: Optional[AsyncCallable|Callable]  = None,
    *,
    propagation: Propagation = Propagation.REQUIRES,
):

    def decorator(func: AsyncCallable|Callable):

        if iscoroutinefunction(unwrap(func)):
            # transactional decorator가 async function에 사용된 경우
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_session = transaction_context.get()

                handler = SessionHandler()

                if current_session is None:
                    current_session = handler.get_manager().get_new_session()

                if propagation == Propagation.REQUIRES:
                    return await _a_do_fn_with_tx(
                        func,
                        current_session  # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                        if current_session
                        else handler.get_manager().get_new_session(),  # 사용 중인 트랜잭션이 없는경우, 새로운 트랜잭션 사용
                        *args,
                        **kwargs,
                    )

                elif propagation == Propagation.REQUIRES_NEW:
                    new_session = handler.get_manager().get_new_session(
                        True
                    )  # 강제로 세션 생성

                    result = await _a_do_fn_with_tx(func, new_session, *args, **kwargs)

                    # 기존 세션으로 복구
                    transaction_context.set(current_session)
                    return result

                elif propagation == Propagation.NESTED:
                    # 사용중인 세션이 있다면 해당 세션을 사용
                    save_point = await current_session.begin_nested()
                    try:
                        kwargs['session'] = current_session
                        result = await func(*args, **kwargs)
                        await current_session.flush()
                        return result
                    except Exception:
                        # 오류 발생 시, save point만 롤백
                        if save_point.is_active:
                            await save_point.rollback()
                        raise

            setattr(async_wrapper, '_transactional_propagation', propagation)
            setattr(async_wrapper, '_transactional_decorated', True)
            return async_wrapper
        else:
            # transactional decorator가 sync function에 사용된 경우
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                current_session = transaction_context.get()

                handler = SessionHandler()

                if current_session is None:
                    current_session = handler.get_manager().get_new_session()

                if propagation == Propagation.REQUIRES:
                    return _do_fn_with_tx(
                        func,
                        current_session  # 이미 트랜잭션을 사용중인 경우 해당 트랜잭션을 사용
                        if current_session
                        else handler.get_manager().get_new_session(),  # 사용 중인 트랜잭션이 없는경우, 새로운 트랜잭션 사용
                        *args,
                        **kwargs,
                    )

                elif propagation == Propagation.REQUIRES_NEW:
                    new_session = handler.get_manager().get_new_session(
                        True
                    )  # 강제로 세션 생성 + 시작

                    result = _do_fn_with_tx(func, new_session, *args, **kwargs)

                    # 기존 세션으로 복구
                    transaction_context.set(current_session)
                    return result

                elif propagation == Propagation.NESTED:
                    # 사용중인 세션이 있다면 해당 세션을 사용
                    save_point = current_session.begin_nested()
                    try:
                        kwargs['session'] = current_session
                        result = func(*args, **kwargs)
                        current_session.flush()
                        return result
                    except Exception:
                        # 오류 발생 시, save point만 롤백
                        if save_point.is_active:
                            save_point.rollback()
                        raise

            setattr(wrapper, '_transactional_propagation', propagation)
            setattr(wrapper, '_transactional_decorated', True)
            return wrapper

    return decorator if _func is None else decorator(_func)
