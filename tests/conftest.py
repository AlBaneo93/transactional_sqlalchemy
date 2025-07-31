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
class TestModel(ORMBase):
    __tablename__ = "test_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


logging.basicConfig(level=logging.INFO)
