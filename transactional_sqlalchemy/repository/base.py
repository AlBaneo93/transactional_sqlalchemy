import logging
from typing import Any, Generic, TypeVar

from sqlalchemy import exists
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column

from transactional_sqlalchemy import ISessionRepository, ITransactionalRepository
from transactional_sqlalchemy.domains import Pageable

MODEL_TYPE = TypeVar("MODEL_TYPE", bound=DeclarativeBase)


class BaseCRUDRepository(Generic[MODEL_TYPE], ISessionRepository):
    def __init__(self, model: type[MODEL_TYPE]) -> None:
        self.model: MODEL_TYPE = model
        self.logger = logging.getLogger(self.__class__.__name__)

    async def find_by_id(self, id: Any, *, session: AsyncSession = None) -> MODEL_TYPE | None:
        pk_column: Column = self.__get_pk_columns()

        stmt: select = select(self.model).where(pk_column == id)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find(self, where: ColumnElement | None = None, *, session: AsyncSession = None) -> MODEL_TYPE | None:
        """
        조건에 맞는 단일 모델을 반환합니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 조건에 맞는 단일 모델 인스턴스 또는 None
        """
        stmt: select = select(self.model)
        if where is None:
            self.logger.warning("Where condition is None, returning all models.")
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find_all(
        self, *, pageable: Pageable | None = None, where: ColumnElement | None = None, session: AsyncSession = None
    ) -> list[MODEL_TYPE]:
        stmt: select = select(self.model)
        stmt = self.__set_where(stmt, where)
        if pageable:
            stmt = stmt.offset(pageable.offset).limit(pageable.limit)
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def find_all_by_id(self, ids: list[Any], *, session: AsyncSession = None) -> list[MODEL_TYPE]:
        pk_column = self.__get_pk_columns()
        stmt: select = select(self.model).where(pk_column.in_(ids))
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def save(self, model: MODEL_TYPE, *, session: AsyncSession = None) -> MODEL_TYPE:
        """
        모델을 저장합니다. 만약 모델에 기본 키 값이 존재한다면, 해당 모델을 업데이트합니다.
        만약 기본 키 값이 존재하지 않는다면, 새로운 모델로 간주하고 추가합니다.
        :param model: 저장할 모델 인스턴스
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 저장된 모델 인스턴스
        :raises ValueError: 모델이 단일 기본 키 컬럼을 가지지 않는 경우
        """
        pk_column: Column = self.__get_pk_columns()
        pk_value = getattr(model, pk_column.name, None)

        if pk_value is not None:
            # 모델에 pk 값이 존재
            is_exists: bool = await self.exists_by_id(pk_value, session=session)
            if is_exists:
                # DB에도 존재하는 경우
                merged_model = await session.merge(model)
                await session.flush([merged_model])
                return merged_model

        session.add(model)
        await session.flush()
        return model

    async def exists(self, where: ColumnElement | None = None, *, session: AsyncSession = None) -> bool:
        """
        조건에 맞는 모델이 존재하는지 확인합니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 조건에 맞는 모델이 존재하면 True, 그렇지 않으면 False
        """
        stmt: select = select(exists().where(where)) if where else select(exists().select_from(self.model))
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def exists_by_id(self, id: Any, *, where: ColumnElement | None = None, session: AsyncSession = None) -> bool:
        pk_column = self.__get_pk_columns()

        stmt: select = select(exists().where(pk_column == id))
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def count(self, *, where: ColumnElement | None = None, session: AsyncSession = None) -> int:
        """
        모델의 총 개수를 반환합니다. 선택적으로 조건을 추가할 수 있습니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 모델의 총 개수
        :raises ValueError: 모델이 단일 기본 키 컬럼을 가지지 않는 경우
        :rtype: int
        """
        pk_column = self.__get_pk_columns()
        stmt: select = select(func.count(pk_column)).select_from(self.model)
        stmt = self.__set_where(stmt, where)
        return await session.scalar(stmt)

    def __get_pk_columns(self) -> Column:
        pk_columns = self.model.__mapper__.primary_key
        if len(pk_columns) != 1:
            raise ValueError("Model must have a single primary key column.")
        pk_column = pk_columns[0]
        return pk_column

    def __set_where(self, stmt: select, where: ColumnElement | None) -> select:
        if where is not None:
            stmt = stmt.where(where)
        return stmt


class BaseCRUDTransactionRepository(BaseCRUDRepository[MODEL_TYPE], ITransactionalRepository): ...
