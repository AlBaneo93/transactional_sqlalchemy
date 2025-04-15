from collections.abc import Awaitable, Callable
from inspect import iscoroutinefunction, unwrap

from src.transactional_sqlalchemy.enums import Propagation
from src.transactional_sqlalchemy.wrapper import __async_transaction_wrapper, __sync_transaction_wrapper

AsyncCallable = Callable[..., Awaitable]



def transactional(
    _func: AsyncCallable | Callable | None = None,
    *,
    propagation: Propagation = Propagation.REQUIRES,
    rollback_for: tuple[type[Exception]] = (Exception,),
    no_rollback_for: tuple[type[Exception, ...]] = (),
):

    def decorator(func: AsyncCallable|Callable):

        if iscoroutinefunction(unwrap(func)):
            # transactional decorator가 async function에 사용된 경우
            async_wrapper = __async_transaction_wrapper(func, propagation, rollback_for, no_rollback_for)

            setattr(async_wrapper, '_transactional_propagation', propagation)
            setattr(async_wrapper, '_transactional_decorated', True)
            return async_wrapper
        else:
            # transactional decorator가 sync function에 사용된 경우
            wrapper = __sync_transaction_wrapper(func, propagation, rollback_for, no_rollback_for)

            setattr(wrapper, '_transactional_propagation', propagation)
            setattr(wrapper, '_transactional_decorated', True)
            return wrapper



    return decorator if _func is None else decorator(_func)
