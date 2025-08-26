"""
동기 환경 테스트 설정
"""

import logging

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from tests.conftest import TestConfig, 데이터베이스_초기화
from transactional_sqlalchemy import init_manager, transaction_context
from transactional_sqlalchemy.utils.structure import Stack


def db_shutdown(sync_engine_: Engine):
    """데이터베이스 연결 종료"""
    sync_engine_.dispose()
    logging.info("[sync] 데이터베이스 연결 종료")


# ===== 동기 환경용 공통 fixture들 =====


@pytest.fixture(scope="module", autouse=True)
def sync_engine_() -> Engine:
    """동기 엔진 생성 및 초기화"""
    engine_kwargs = TestConfig.get_engine_kwargs("sync")
    sync_engine_ = create_engine(TestConfig.get_database_url("sync"), **engine_kwargs)

    # 데이터베이스 초기화
    데이터베이스_초기화(sync_engine_)

    yield sync_engine_
    db_shutdown(sync_engine_)


@pytest.fixture(scope="function", autouse=True)
def session_factory_(sync_engine_: Engine) -> sessionmaker:
    """동기 세션 팩토리 생성"""
    return sessionmaker(sync_engine_, expire_on_commit=False)


@pytest.fixture(scope="function", autouse=True)
def scoped_session_(session_factory_: sessionmaker) -> scoped_session:
    """스코프된 세션 생성"""
    session = scoped_session(session_factory_)
    session.begin()
    yield session

    session.rollback()
    session.remove()


@pytest.fixture(scope="function", autouse=True)
def session_start_up(scoped_session_: scoped_session) -> None:
    """세션 매니저 초기화"""
    init_manager(scoped_session_)
    logging.info("[sync] 세션 매니저 초기화 완료")


@pytest.fixture(scope="function", autouse=True)
def transaction_sync(scoped_session_: scoped_session, session_start_up) -> Session:
    """동기 트랜잭션 세션 생성"""
    sess = scoped_session_()
    s = Stack()
    s.push(sess)
    transaction_context.set(s)

    logging.info("[sync] 트랜잭션 시작")
    return sess
