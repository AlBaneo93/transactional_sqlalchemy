"""
비동기 환경 테스트 설정
"""

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

from tests.conftest import ORMBase, TestConfig
from transactional_sqlalchemy import init_manager
from transactional_sqlalchemy.utils.transaction_util import add_session_to_context

# ===== 비동기 환경용 공통 fixture들 =====


@pytest_asyncio.fixture(scope="function", autouse=True)
async def async_engine_() -> AsyncEngine:
    """비동기 엔진 생성 및 초기화"""
    engine_kwargs = TestConfig.get_engine_kwargs("async")
    async_engine_ = create_async_engine(TestConfig.get_database_url("async"), **engine_kwargs)

    # 데이터베이스 초기화
    async with async_engine_.begin() as conn:
        await conn.run_sync(ORMBase.metadata.create_all)

    yield async_engine_
    await async_engine_.dispose()


@pytest.fixture(scope="function", autouse=True)
def session_factory_(async_engine_: AsyncEngine) -> async_sessionmaker:
    """비동기 세션 팩토리 생성"""
    return async_sessionmaker(async_engine_, expire_on_commit=False)


@pytest.fixture(scope="function", autouse=True)
def scoped_session_(session_factory_: async_sessionmaker) -> async_scoped_session:
    """스코프된 세션 생성"""
    return async_scoped_session(session_factory_, scopefunc=asyncio.current_task)


@pytest.fixture(scope="function", autouse=True)
def session_start_up(scoped_session_: async_scoped_session) -> None:
    """세션 매니저 초기화"""
    init_manager(scoped_session_)
    logging.info("[async] 세션 매니저 초기화 완료")


@pytest_asyncio.fixture(scope="function", autouse=True)
async def transaction_async(scoped_session_: async_scoped_session, session_start_up) -> AsyncSession:
    """비동기 트랜잭션 세션 생성"""
    sess = scoped_session_()
    add_session_to_context(sess)

    await sess.begin()
    logging.info("[async] 트랜잭션 시작")

    return sess
