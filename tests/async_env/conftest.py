import asyncio
import logging

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool.impl import StaticPool

from tests.conftest import ORMBase
from transactional_sqlalchemy import init_manager
from transactional_sqlalchemy.utils.utils import add_session_to_context


@pytest_asyncio.fixture(scope="function", autouse=True)
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
    add_session_to_context(sess)

    await sess.begin()

    logging.info("Transaction started")
    return sess
