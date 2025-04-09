import functools

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from config import transaction_context


def with_transaction_context(func):
    """함수의 session 파라미터를 자동으로 transaction_context에서 가져오도록 설정하는 데코레이터"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 함수의 인자에 `session: AsyncSession | Session`이 포함되어 있다면 자동 할당
        if "session" in func.__annotations__ and func.__annotations__["session"] in [
            AsyncSession,
            Session,
        ]:
            if "session" not in kwargs or kwargs["session"] is None:
                kwargs["session"] = transaction_context.get()

        return await func(*args, **kwargs)

    return wrapper
