import functools
import logging
from asyncio import iscoroutinefunction
from enum import Enum
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction
from sqlalchemy.orm import Session, SessionTransaction

from config import SessionHandler, transaction_context

AsyncCallable = Callable[..., Awaitable]


class Propagation(Enum):
    REQUIRES = "REQUIRES"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"


async def _a_do_fn_with_tx(func, session: AsyncSession, *args, **kwargs):
    tx: AsyncSessionTransaction = await session.begin()  # 트랜잭션 명시적 시작
    transaction_context.set(session)

    try:
        kwargs["session"] = session
        result = await func(*args, **kwargs)
        if tx.is_active:
            # 트랜잭션이 활성화 되어 있다면 커밋
            await tx.commit()
        return result
    except:
        logging.exception("")
        if tx.is_active:
            await tx.rollback()
        raise
    finally:
        await session.aclose()
        transaction_context.set(None)


def _do_fn_with_tx(func, session: Session, *args, **kwargs):
    tx: SessionTransaction = session.get_transaction()  # 시작 되어 넘어옴
    # tx: SessionTransaction = session.begin()  # 트랜잭션 명시적 시작
    if tx is None:
        tx = session.begin()
    transaction_context.set(session)

    try:
        kwargs["session"] = session
        result = func(*args, **kwargs)
        if tx.is_active:
            tx.commit()
        return result
    except:
        logging.exception("")
        if tx.is_active:
            tx.rollback()
        raise
    finally:
        session.close()
        transaction_context.set(None)


def transactional(
    _func: AsyncCallable | None = None,
    *,
    propagation: Propagation = Propagation.REQUIRES,
):
    def decorator(func: AsyncCallable):
        if iscoroutinefunction(func):
            # transactional decorator가 async function에 사용된 경우
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
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
                        kwargs["session"] = current_session
                        result = await func(*args, **kwargs)
                        await current_session.flush()
                        return result
                    except Exception:
                        # 오류 발생 시, save point만 롤백
                        if save_point.is_active:
                            await save_point.rollback()
                        raise

            transaction_func = wrapper
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
                        kwargs["session"] = current_session
                        result = func(*args, **kwargs)
                        current_session.flush()
                        return result
                    except Exception:
                        # 오류 발생 시, save point만 롤백
                        if save_point.is_active:
                            save_point.rollback()
                        raise

            transaction_func = wrapper

        setattr(transaction_func, "_transactional_propagation", propagation)
        setattr(transaction_func, "_transactional_decorated", True)
        return transaction_func

    if _func is None:
        return decorator
    else:
        return decorator(_func)
