import functools
import inspect
from inspect import iscoroutinefunction, unwrap

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from transactional_sqlalchemy.config import SessionHandler, transaction_context


def allocate_session_in_args(bound_args: inspect.BoundArguments):
    if 'session' in bound_args.arguments:
        sess = bound_args.arguments['session']
        if sess is None or (sess is not None and isinstance(sess, (Session, AsyncSession))):
            new_session = transaction_context.get() or SessionHandler().get_manager().get_new_session()
            bound_args.arguments['session'] = new_session


def with_transaction_context(func):
    """함수의 session 파라미터를 자동으로 transaction_context에서 가져오도록 설정하는 데코레이터"""
    sig = inspect.signature(func)

    if iscoroutinefunction(unwrap(func)):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            allocate_session_in_args(bound_args)

            return await func(*bound_args.args, **bound_args.kwargs)
        return async_wrapper
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            allocate_session_in_args(bound_args)

            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper