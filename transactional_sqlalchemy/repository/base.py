from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, get_args, get_origin

from sqlalchemy import exists
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.decl_api import DeclarativeBase, DeclarativeMeta
from sqlalchemy.orm.strategy_options import Load
from sqlalchemy.sql.elements import ColumnElement, and_, or_
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.selectable import Select

from transactional_sqlalchemy import ISessionRepository, ITransactionalRepository
from transactional_sqlalchemy.domains import Pageable
from transactional_sqlalchemy.utils.common import get_logger

MODEL_TYPE = TypeVar("MODEL_TYPE", bound=DeclarativeBase)

# 복합키를 위한 타입 정의
CompositeKeyType = dict[str, Any]
PrimaryKeyType = Any | CompositeKeyType


@dataclass(frozen=True)
class CompositeKey:
    """복합키를 표현하는 데이터클래스.

    SQLAlchemy 모델의 복합 기본 키를 표현하고 처리하기 위한 데이터클래스입니다.

    Attributes:
        values (dict[str, Any]): 컬럼 이름과 값의 매핑
    """

    values: dict[str, Any]

    def to_tuple(self, column_order: list[str]) -> tuple[Any, ...]:
        """지정된 컬럼 순서에 따라 튜플로 변환합니다.

        Args:
            column_order (list[str]): 컬럼들의 순서

        Returns:
            tuple[Any, ...]: 지정된 순서로 정렬된 값들의 튜플
        """
        return tuple(self.values[col] for col in column_order)

    @classmethod
    def from_model(cls, model: DeclarativeBase, pk_columns: list[str]) -> CompositeKey:
        """모델 인스턴스에서 복합키를 생성합니다.

        Args:
            model (DeclarativeBase): SQLAlchemy 모델 인스턴스
            pk_columns (list[str]): 기본 키 컬럼 이름 목록

        Returns:
            CompositeKey: 생성된 복합키 인스턴스
        """
        values = {col: getattr(model, col) for col in pk_columns}
        return cls(values)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


class BaseCRUDRepository(Generic[MODEL_TYPE], ISessionRepository):
    def __init_subclass__(cls):
        """서브클래스 생성시 model을 클래스 변수로 설정합니다."""
        super().__init_subclass__()
        cls._model = cls.__extract_model_from_generic()

    def __init__(self):
        self.logger = get_logger()

    @classmethod
    def __extract_model_from_generic(cls) -> type[MODEL_TYPE] | None:
        """Generic 타입 파라미터에서 모델 타입을 추출합니다.

        Returns:
            type[MODEL_TYPE] | None: 추출된 모델 타입 또는 None
        """
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
        """단일 키 또는 복합키로 모델을 조회합니다.

        Args:
            id (PrimaryKeyType): 단일 키값 또는 복합키 딕셔너리 {"col1": val1, "col2": val2}
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            MODEL_TYPE | None: 조회된 모델 인스턴스 또는 None
        """
        stmt = self.__get_select_query().where(self.__build_pk_condition(id))
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find(self, where: ColumnElement | None = None, *, session: AsyncSession) -> MODEL_TYPE | None:
        """조건에 맞는 단일 모델을 반환합니다.

        Args:
            where (ColumnElement | None): 조건을 추가할 수 있는 ColumnElement
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            MODEL_TYPE | None: 조건에 맞는 단일 모델 인스턴스 또는 None
        """
        stmt = self.__get_select_query()
        if where is None:
            self.logger.warning("Where condition is None, returning all models.")
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar_one_or_none()

    async def find_all(
        self, *, pageable: Pageable | None = None, where: ColumnElement | None = None, session: AsyncSession
    ) -> list[MODEL_TYPE]:
        """조건에 맞는 모든 모델을 조회합니다.

        Args:
            pageable (Pageable | None): 페이징 정보
            where (ColumnElement | None): 조건을 추가할 수 있는 ColumnElement
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            list[MODEL_TYPE]: 조건에 맞는 모델 인스턴스 목록
        """
        stmt = self.__get_select_query()
        stmt = self.__set_where(stmt, where)
        if pageable:
            stmt = stmt.offset(pageable.offset).limit(pageable.limit)
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def find_all_by_id(self, ids: list[PrimaryKeyType], *, session: AsyncSession) -> list[MODEL_TYPE]:
        """여러 개의 키로 모델들을 조회합니다.

        Args:
            ids (list[PrimaryKeyType]): 조회할 키 목록 (단일키 또는 복합키 지원)
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            list[MODEL_TYPE]: 조회된 모델 인스턴스 목록
        """
        if not ids:
            return []

        conditions = [self.__build_pk_condition(pk_id) for pk_id in ids]
        stmt = self.__get_select_query().where(or_(*conditions))
        query_result: Result = await session.execute(stmt)
        return list(query_result.scalars().all())

    async def save(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        """모델을 저장합니다.

        단일키와 복합키를 모두 지원하며, 기존 데이터가 있으면 업데이트,
        없으면 삽입됩니다.

        Args:
            model (MODEL_TYPE): 저장할 모델 인스턴스
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            MODEL_TYPE: 저장된 모델 인스턴스
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
        """조건에 맞는 모델이 존재하는지 확인합니다.

        Args:
            where (ColumnElement | None): 조건을 추가할 수 있는 ColumnElement
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            bool: 조건에 맞는 모델이 존재하면 True, 그렇지 않으면 False
        """
        stmt = select(exists().where(where)) if where else select(exists().select_from(self.__get_model()))
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def exists_by_id(
        self, id: PrimaryKeyType, *, where: ColumnElement | None = None, session: AsyncSession
    ) -> bool:
        """단일 키 또는 복합키로 모델이 존재하는지 확인합니다.

        Args:
            id (PrimaryKeyType): 단일 키값 또는 복합키 딕셔너리
            where (ColumnElement | None): 추가 조건
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            bool: 모델이 존재하면 True, 그렇지 않으면 False
        """
        pk_condition = self.__build_pk_condition(id)
        stmt = select(exists().where(pk_condition))
        stmt = self.__set_where(stmt, where)
        query_result: Result = await session.execute(stmt)
        return query_result.scalar()

    async def count(self, *, where: ColumnElement | None = None, session: AsyncSession) -> int:
        """모델의 총 개수를 반환합니다.

        Args:
            where (ColumnElement | None): 조건을 추가할 수 있는 ColumnElement
            session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

        Returns:
            int: 모델의 총 개수
        """
        pk_columns = self.__get_pk_columns()
        # 첫 번째 pk 컬럼을 사용해서 count
        stmt = select(func.count(pk_columns[0])).select_from(self.__get_model())
        stmt = self.__set_where(stmt, where)
        return await session.scalar(stmt)

    def __get_pk_columns(self) -> list[Column]:
        """기본 키 컬럼들을 반환합니다.

        Returns:
            list[Column]: 모델의 기본 키 컬럼 목록

        Raises:
            ValueError: 모델에 기본 키가 없는 경우
        """
        pk_columns = list(self.__get_model().__mapper__.primary_key)
        if not pk_columns:
            raise ValueError("Model must have at least one primary key column.")
        return pk_columns

    def _is_single_pk(self) -> bool:
        """단일 기본 키인지 확인합니다.

        Returns:
            bool: 단일 기본 키이면 True, 복합 기본 키이면 False
        """
        return len(self.__get_pk_columns()) == 1

    @classmethod
    def __set_where(cls, stmt: select, where: ColumnElement | None) -> select:
        if where is not None:
            stmt = stmt.where(where)
        return stmt

    def __get_model(self) -> type[MODEL_TYPE]:
        """제네릭 타입 T에 바인딩된 실제 모델 클래스를 찾아 반환합니다.

        __orig_bases__를 순회하여 더 안정적으로 타입을 찾습니다.

        Returns:
            type[MODEL_TYPE]: 제네릭 타입에 바인딩된 모델 클래스

        Raises:
            TypeError: 제네릭 타입 T에 대한 모델 클래스를 찾을 수 없는 경우
        """
        for base in self.__class__.__orig_bases__:
            # 제네릭 타입의 인자(arguments)를 가져옵니다.
            args = get_args(base)
            if args:
                return args[0]
        raise TypeError("제네릭 타입 T에 대한 모델 클래스를 찾을 수 없습니다.")

    def __get_pk_values_from_model(self, model: MODEL_TYPE) -> PrimaryKeyType:
        """모델에서 기본 키 값들을 추출합니다.

        단일 PK인 경우 값만 반환하고, 복합키인 경우 딕셔너리로 반환합니다.

        Args:
            model (MODEL_TYPE): 기본 키 값을 추출할 모델 인스턴스

        Returns:
            PrimaryKeyType: 단일 키의 경우 값, 복합키의 경우 딕셔너리
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
        """모든 기본 키 값이 존재하는지 확인합니다.

        Args:
            pk_values (PrimaryKeyType): 확인할 기본 키 값들

        Returns:
            bool: 모든 기본 키 값이 존재하면 True, 그렇지 않으면 False
        """
        if isinstance(pk_values, dict):
            return all(val is not None for val in pk_values.values())
        else:
            return pk_values is not None

    def __build_pk_condition(self, pk_value: PrimaryKeyType) -> ColumnElement:
        """기본 키 조건을 생성합니다.

        단일키와 복합키를 모두 지원합니다.

        Args:
            pk_value (PrimaryKeyType): 단일 PK는 값만, 복합키는 딕셔너리 {"col1": val1, "col2": val2}

        Returns:
            ColumnElement: WHERE 절에 사용할 수 있는 조건 요소

        Raises:
            ValueError: 단일 키에 딕셔너리를 전달하거나, 복합키에 누락된 컬럼이 있는 경우
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

    def __build_unique_selectinload_options(
        self, model_cls: type[DeclarativeMeta], visited: set[type[DeclarativeMeta]] = None, depth: int | None = 1
    ) -> list[Load]:
        """
        재귀적으로 관계를 따라가며 selectinload 로딩 옵션을 생성하되,
        이미 방문한 모델은 제외하고 지정된 depth까지만 탐색한다.

        :param model_cls: SQLAlchemy Declarative 모델 클래스
        :param visited: 이미 방문한 모델 클래스 집합
        :param depth: 탐색할 최대 depth (1 = 바로 하위 관계만, None = 무한 깊이)
        :return: SQLAlchemy Load 옵션 리스트 (selectinload(...))
        """
        if visited is None:
            visited = set()

        if model_cls in visited or (depth is not None and depth < 1):
            return []

        visited.add(model_cls)

        options: list[Load] = []
        mapper = inspect(model_cls)

        for rel in mapper.relationships:
            attr = getattr(model_cls, rel.key)
            target_cls: type[DeclarativeMeta] = rel.mapper.class_

            # 하위 관계 옵션 생성 (depth-1로 재귀, depth가 None이면 그대로 전달)
            suboptions = self.__build_unique_selectinload_options(
                model_cls=target_cls,
                visited=visited.copy(),  # 복사해서 하위에서 중복 방지 유지
                depth=depth - 1 if depth is not None else None,
            )

            loader = selectinload(attr)
            if suboptions:
                loader = loader.options(*suboptions)

            options.append(loader)

        return options

    def __get_select_query(self) -> Select[tuple[MODEL_TYPE]]:
        """현재 모델에 대한 기본 select 쿼리를 생성합니다.

        자동으로 모든 관계에 대한 selectinload 옵션을 적용하여
        N+1 쿼리 문제를 방지합니다.

        Returns:
            Select[tuple[MODEL_TYPE]]: SQLAlchemy select 쿼리 객체
        """
        model_type: MODEL_TYPE = self.__get_model()
        return select(model_type).options(*self.__build_unique_selectinload_options(model_type))


class BaseCRUDTransactionRepository(BaseCRUDRepository[MODEL_TYPE], ITransactionalRepository): ...
