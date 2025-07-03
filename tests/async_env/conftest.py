import asyncio
import logging
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.pool.impl import StaticPool

from tests.conftest import ORMBase
from transactional_sqlalchemy import init_manager, transaction_context

# @pytest.fixture(scope='function')
# def event_loop():
#     """Create an instance of the default event loop for each test module."""
#     loop = asyncio.new_event_loop()
#     yield loop
#     loop.close()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def async_engine_():
    async_engine_ = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
        # 변경!
        connect_args={"check_same_thread": False},  # 필요시 추가)
    )
    async with async_engine_.begin() as conn:
        await conn.run_sync(ORMBase.metadata.create_all)

    yield async_engine_
    await async_engine_.dispose()


@pytest.fixture(scope="function", autouse=True)
def session_factory_(async_engine_: AsyncEngine) -> async_sessionmaker:
    async_session_factory = async_sessionmaker(async_engine_, expire_on_commit=False)
    return async_session_factory


@pytest.fixture(scope="function", autouse=True)
def scoped_session_(session_factory_) -> async_scoped_session:
    return async_scoped_session(session_factory_, scopefunc=asyncio.current_task)


@pytest.fixture(scope="function", autouse=True)
def session_start_up(scoped_session_: async_scoped_session) -> None:
    init_manager(scoped_session_)
    logging.info("Session initialized")


@pytest_asyncio.fixture(scope="function", autouse=True)
async def transaction_async(scoped_session_: async_scoped_session, session_start_up) -> AsyncSession:
    sess = scoped_session_()
    transaction_context.set(sess)
    await sess.begin()

    logging.info("Transaction started")
    return sess


class Post(ORMBase):
    __tablename__ = "post_async"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# 테스트용 모델 정의
class TestModel(ORMBase):
    __tablename__ = "test_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
