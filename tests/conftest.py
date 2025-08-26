"""
공통 테스트 설정 및 모델 정의
"""

import logging
from datetime import datetime

from sqlalchemy.orm import mapped_column
from sqlalchemy.orm.attributes import Mapped
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.sqltypes import DateTime, Integer, String, Text

# 로깅 설정
logging.basicConfig(level=logging.INFO)


class ORMBase(DeclarativeBase):
    """모든 ORM 모델의 베이스 클래스"""

    pass


# ===== 메인 테스트 모델들 =====


class Post(ORMBase):
    """포스트 모델 - 트랜잭션 테스트용"""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SampleModel(ORMBase):
    """단순 테스트 모델"""

    __tablename__ = "sample_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


# ===== 복합키 테스트 모델들 =====


class OrderItem(ORMBase):
    """주문 아이템 모델 - 복합키 테스트용"""

    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[int] = mapped_column(Integer, default=0)


class UserRolePermission(ORMBase):
    """사용자 권한 모델 - 3개 컬럼 복합키 테스트용"""

    __tablename__ = "user_role_permissions"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ===== 테스트 환경별 설정 =====


class TestConfig:
    """테스트 환경 설정"""

    @staticmethod
    def get_database_url(env_type: str = "async") -> str:
        """환경별 데이터베이스 URL 반환"""
        if env_type == "async":
            return "sqlite+aiosqlite:///:memory:"
        elif env_type == "sync":
            return "sqlite:///:memory:"
        else:
            raise ValueError(f"지원하지 않는 환경 타입: {env_type}")

    @staticmethod
    def get_engine_kwargs(env_type: str = "async") -> dict:
        """환경별 엔진 설정 반환"""
        if env_type == "async":
            from sqlalchemy.pool.impl import StaticPool

            return {
                "echo": False,
                "future": True,
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        elif env_type == "sync":
            return {"echo": False}
        else:
            raise ValueError(f"지원하지 않는 환경 타입: {env_type}")


# ===== 공통 헬퍼 함수들 =====


def 데이터베이스_초기화(engine, base_class=ORMBase):
    """데이터베이스 테이블 생성"""
    with engine.begin() as conn:
        base_class.metadata.create_all(conn)


def 데이터베이스_정리(engine, base_class=ORMBase):
    """데이터베이스 테이블 삭제"""
    with engine.begin() as conn:
        base_class.metadata.drop_all(conn)
