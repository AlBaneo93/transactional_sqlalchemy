import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import DateTime, func, Integer, String, Text, URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, mapped_column, Session, declarative_base

from config import init_manager, transaction_context

ORMBase = declarative_base()


async def db_startup(async_engine_: AsyncEngine):
    # db init
    async with async_engine_.begin() as conn:
        await conn.run_sync(ORMBase.metadata.create_all)

    logging.info("DB initialized")


async def db_shutdown(async_engine_: AsyncEngine):
    # db close
    await async_engine_.dispose()
    logging.info("DB disposed")


@pytest.fixture(scope="session", autouse=True)
def async_engine_() -> AsyncEngine:
    DB_URL = "sqlite+aiosqlite:///:memory:"
    async_engine_ = create_async_engine(DB_URL, echo=True, future=True)
    asyncio.run(db_startup(async_engine_))
    return async_engine_


@pytest.fixture(scope="session", autouse=True)
def session_factory_(async_engine_: AsyncEngine) -> async_sessionmaker:
    async_session_factory = async_sessionmaker(async_engine_, expire_on_commit=False)
    return async_session_factory


@pytest.fixture(scope="session", autouse=True)
def scoped_session_(session_factory_) -> async_scoped_session:
    async_scoped_session_ = async_scoped_session(
        session_factory_, scopefunc=asyncio.current_task
    )

    return async_scoped_session_


@pytest.fixture(scope="function", autouse=True)
def session_start_up(scoped_session_: async_scoped_session) -> None:
    init_manager(scoped_session_)
    logging.info("Session initialized")


@pytest_asyncio.fixture(scope="function", autouse=True)
async def transaction(
    scoped_session_: async_scoped_session, session_start_up
) -> AsyncSession:
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
