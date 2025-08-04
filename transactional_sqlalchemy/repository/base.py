from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, get_args, get_origin

from sqlalchemy import exists
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.sql.elements import ColumnElement, and_, or_
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column

from transactional_sqlalchemy import ISessionRepository, ITransactionalRepository
from transactional_sqlalchemy.domains import Pageable
from transactional_sqlalchemy.utils.common import get_logger

MODEL_TYPE = TypeVar("MODEL_TYPE", bound=DeclarativeBase)

# 복합키를 위한 타입 정의
CompositeKeyType = dict[str, Any]
PrimaryKeyType = Any | CompositeKeyType


@dataclass(frozen=True)
class CompositeKey:
    """
    복합키를 표현하는 데이터클래스
    """

    values: dict[str, Any]

    def to_tuple(self, column_order: list[str]) -> tuple[Any, ...]:
        """지정된 컬럼 순서에 따라 튜플로 변환"""
        return tuple(self.values[col] for col in column_order)

    @classmethod
    def from_model(cls, model: DeclarativeBase, pk_columns: list[str]) -> CompositeKey:
        """모델 인스턴스에서 복합키 생성"""
        values = {col: getattr(model, col) for col in pk_columns}
        return cls(values)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


class BaseCRUDRepository(Generic[MODEL_TYPE], ISessionRepository):
    def __init_subclass__(cls):
        """서브클래스 생성시 model을 클래스 변수로 설정"""
        super().__init_subclass__()
        cls._model = cls.__extract_model_from_generic()

    def __init__(self):
        self.logger = get_logger()

    @classmethod
    def __extract_model_from_generic(cls) -> type[MODEL_TYPE] | None:
        """Generic 타입 파라미터에서 모델 타입 추출"""
        # 방법 1: __orig_bases__ 확인
        if hasattr(cls, "__orig_bases__"):
            for base in cls.__orig_bases__:
                origin = get_origin(base)
                # 더 유연한 비교
                if origin is not None and (
                    origin is BaseCRUDRepository
                    or (hasattr(origin, "__name__") and origin.__name__ == "BaseCRUDRepository")
                ):
                    args = get_args(base)
                    if args and len(args) > 0:
                        return args[0]

        # 방법 2: __args__ 확인 (Generic[T] 형태)
        if hasattr(cls, "__args__") and cls.__args__:
            return cls.__args__[0]

    async def find_by_id(self, id: PrimaryKeyType, *, session: AsyncSession) -> MODEL_TYPE | None:
        """
        단일 키 또는 복합키로 모델을 조회합니다.
        :param id: 단일 키값 또는 복합키 딕셔너리 {"col1": val1, "col2": val2}
        """
        model = self.__get_model()
        stmt = select(model).where(self.__build_pk_condition(id))
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find(self, where: ColumnElement | None = None, *, session: AsyncSession) -> MODEL_TYPE | None:
        """
        조건에 맞는 단일 모델을 반환합니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 조건에 맞는 단일 모델 인스턴스 또는 None
        """
        stmt = select(self.__get_model())
        if where is None:
            self.logger.warning("Where condition is None, returning all models.")
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find_all(
        self, *, pageable: Pageable | None = None, where: ColumnElement | None = None, session: AsyncSession
    ) -> list[MODEL_TYPE]:
        stmt = select(self.__get_model())
        stmt = self.__set_where(stmt, where)
        if pageable:
            stmt = stmt.offset(pageable.offset).limit(pageable.limit)
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def find_all_by_id(self, ids: list[PrimaryKeyType], *, session: AsyncSession) -> list[MODEL_TYPE]:
        """
        여러 개의 키로 모델들을 조회합니다. (단일키 또는 복합키 지원)
        """
        if not ids:
            return []

        model = self.__get_model()
        conditions = [self.__build_pk_condition(pk_id) for pk_id in ids]
        stmt = select(model).where(or_(*conditions))
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def save(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        """
        모델을 저장합니다. 단일키와 복합키 모두 지원합니다.
        """
        pk_values = self.__get_pk_values_from_model(model)

        if self.__has_all_pk_values(pk_values):
            # 모델에 pk 값이 존재
            is_exists: bool = await self.exists_by_id(pk_values, session=session)
            if is_exists:
                # DB에도 존재하는 경우
                merged_model = await session.merge(model)
                await session.flush([merged_model])
                return merged_model

        session.add(model)
        await session.flush()
        return model

    async def exists(self, where: ColumnElement | None = None, *, session: AsyncSession) -> bool:
        """
        조건에 맞는 모델이 존재하는지 확인합니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 조건에 맞는 모델이 존재하면 True, 그렇지 않으면 False
        """
        stmt = select(exists().where(where)) if where else select(exists().select_from(self.__get_model()))
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def exists_by_id(
        self, id: PrimaryKeyType, *, where: ColumnElement | None = None, session: AsyncSession
    ) -> bool:
        """
        단일 키 또는 복합키로 모델이 존재하는지 확인합니다.
        """
        pk_condition = self.__build_pk_condition(id)
        stmt = select(exists().where(pk_condition))
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def count(self, *, where: ColumnElement | None = None, session: AsyncSession) -> int:
        """
        모델의 총 개수를 반환합니다. 선택적으로 조건을 추가할 수 있습니다.
        :param where: 조건을 추가할 수 있는 ColumnElement
        :param session: SQLAlchemy의 AsyncSession 인스턴스
        :return: 모델의 총 개수
        :rtype: int
        """
        pk_columns = self.__get_pk_columns()
        # 첫 번째 pk 컬럼을 사용해서 count
        stmt = select(func.count(pk_columns[0])).select_from(self.__get_model())
        stmt = self.__set_where(stmt, where)
        return await session.scalar(stmt)

    def __get_pk_columns(self) -> list[Column]:
        """기본 키 컬럼들을 반환합니다."""
        pk_columns = list(self.__get_model().__mapper__.primary_key)
        if not pk_columns:
            raise ValueError("Model must have at least one primary key column.")
        return pk_columns

    def _is_single_pk(self) -> bool:
        """단일 기본 키인지 확인합니다."""
        return len(self.__get_pk_columns()) == 1

    @classmethod
    def __set_where(cls, stmt: select, where: ColumnElement | None) -> select:
        if where is not None:
            stmt = stmt.where(where)
        return stmt

    def __get_model(self) -> type[MODEL_TYPE]:
        """
        제네릭 타입 T에 바인딩된 실제 모델 클래스를 찾아 반환합니다.
        __orig_bases__를 순회하여 더 안정적으로 타입을 찾습니다.
        """
        for base in self.__class__.__orig_bases__:
            # 제네릭 타입의 인자(arguments)를 가져옵니다.
            args = get_args(base)
            if args:
                return args[0]
        raise TypeError("제네릭 타입 T에 대한 모델 클래스를 찾을 수 없습니다.")

    def __get_pk_values_from_model(self, model: MODEL_TYPE) -> PrimaryKeyType:
        """
        모델에서 기본 키 값들을 추출합니다.
        단일 PK: 값만 반환
        복합키: 딕셔너리로 반환
        """
        pk_columns = self.__get_pk_columns()

        if len(pk_columns) == 1:
            # 단일 기본 키
            return getattr(model, pk_columns[0].name, None)
        else:
            # 복합 기본 키 - 딕셔너리로 반환
            pk_dict = {}
            for col in pk_columns:
                pk_dict[col.name] = getattr(model, col.name, None)
            return pk_dict

    @classmethod
    def __has_all_pk_values(cls, pk_values: PrimaryKeyType) -> bool:
        """
        모든 기본 키 값이 존재하는지 확인합니다.
        """
        if isinstance(pk_values, dict):
            return all(val is not None for val in pk_values.values())
        else:
            return pk_values is not None

    def __build_pk_condition(self, pk_value: PrimaryKeyType) -> ColumnElement:
        """
        기본 키 조건을 생성합니다. 단일키와 복합키 모두 지원합니다.
        단일 PK: 값만 받음
        복합키: 딕셔너리만 받음 {"col1": val1, "col2": val2}
        """
        pk_columns = self.__get_pk_columns()

        if len(pk_columns) == 1:
            # 단일 기본 키
            if isinstance(pk_value, dict):
                raise ValueError("Single primary key should not be a dictionary")
            return pk_columns[0] == pk_value
        else:
            # 복합 기본 키 - 딕셔너리만 허용
            if not isinstance(pk_value, dict):
                raise ValueError("Composite primary key must be a dictionary with column names as keys")

            conditions = []
            for col in pk_columns:
                if col.name not in pk_value:
                    raise ValueError(f"Missing primary key value for column: {col.name}")
                conditions.append(col == pk_value[col.name])
            return and_(*conditions)


class BaseCRUDTransactionRepository(BaseCRUDRepository[MODEL_TYPE], ITransactionalRepository): ...
