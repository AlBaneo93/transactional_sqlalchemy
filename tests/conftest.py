import logging
from datetime import datetime

from sqlalchemy.orm import mapped_column
from sqlalchemy.orm.attributes import Mapped
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.sqltypes import DateTime, Integer, String, Text


class ORMBase(DeclarativeBase):
    pass


class Post(ORMBase):
    __tablename__ = "post_async"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# 테스트용 모델 정의
class SampleModel(ORMBase):
    __tablename__ = "test_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


# 복합키 테스트용 모델
class OrderItem(ORMBase):
    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[int] = mapped_column(Integer, default=0)


# 복합키 (3개 컬럼) 테스트용 모델
class UserRolePermission(ORMBase):
    __tablename__ = "user_role_permissions"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


logging.basicConfig(level=logging.INFO)
