from typing import Any, Generic, TypeVar

from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column

from transactional_sqlalchemy import ISessionRepository, ITransactionalRepository
from transactional_sqlalchemy.enums import Pageable

MODEL_TYPE = TypeVar("MODEL_TYPE", bound=DeclarativeBase)


class BaseCRUDRepository(Generic[MODEL_TYPE], ISessionRepository):
    def __init__(self, model: type[MODEL_TYPE]) -> None:
        self.model: MODEL_TYPE = model

    async def find_by_id(self, id: Any, *, session: AsyncSession) -> MODEL_TYPE | None:
        pk_column: Column = self.__get_pk_columns()

        stmt: select = select(self.model).where(pk_column == id)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find_all(self, *, pageable: Pageable | None = None, session: AsyncSession) -> list[MODEL_TYPE]:
        stmt: select = select(self.model)
        if pageable:
            stmt = stmt.offset(pageable.page).limit(pageable.size)
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def find_all_by_id(self, ids: list[Any], *, session: AsyncSession) -> list[MODEL_TYPE]:
        pk_column = self.__get_pk_columns()
        stmt: select = select(self.model).where(pk_column.in_(ids))
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    # TODO 2025-07-03 22:46:26 : Upsert를 지원하도록 하면 좋아보임
    async def save(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        session.add(model)
        # await session.flush()
        return model

    # TODO 2025-07-03 22:46:26 : Upsert를 지원하도록 하면 좋아보임
    async def save_all(self, models: list[MODEL_TYPE], *, session: AsyncSession) -> list[MODEL_TYPE]:
        session.add_all(models)
        # await session.flush()
        return models

    async def exists_by_id(self, id: Any, *, session: AsyncSession) -> bool:
        pk_column = self.__get_pk_columns()

        stmt: select = select(self.model).where(pk_column == id)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none() is not None

    async def count(self, *, session: AsyncSession) -> int:
        pk_column = self.__get_pk_columns()
        stmt: select = select(func.count(pk_column)).select_from(self.model)
        return await session.scalar(stmt)

    def __get_pk_columns(self) -> Column:
        pk_columns = self.model.__mapper__.primary_key
        if len(pk_columns) != 1:
            raise ValueError("Model must have a single primary key column.")
        pk_column = pk_columns[0]
        return pk_column


class BaseCRUDTransactionRepository(BaseCRUDRepository[MODEL_TYPE], ITransactionalRepository): ...
