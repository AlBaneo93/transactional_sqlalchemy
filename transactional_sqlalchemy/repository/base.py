from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union, get_args, get_origin

from sqlalchemy import exists
from sqlalchemy.engine.result import Result
from sqlalchemy.future import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.decl_api import DeclarativeBase, DeclarativeMeta
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.strategy_options import _AbstractLoad
from sqlalchemy.sql.elements import ColumnElement, and_, or_
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.selectable import Select

from transactional_sqlalchemy import ISessionRepository, ITransactionalRepository
from transactional_sqlalchemy.config import HAS_ASYNC_SUPPORT
from transactional_sqlalchemy.decorator.transactional import transactional
from transactional_sqlalchemy.utils.common import get_logger

MODEL_TYPE = TypeVar("MODEL_TYPE", bound=DeclarativeBase)

# 복합키를 위한 타입 정의
CompositeKeyType = dict[str, Any]
PrimaryKeyType = Union[Any, CompositeKeyType]


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


class RepositoryUtil:
    def __init__(self):
        self.logger = get_logger()

    def _get_pk_columns(self) -> list[Column]:
        """기본 키 컬럼들을 반환합니다.

        Returns:
            list[Column]: 모델의 기본 키 컬럼 목록

        Raises:
            ValueError: 모델에 기본 키가 없는 경우
        """
        pk_columns = list(self._get_model().__mapper__.primary_key)
        if not pk_columns:
            raise ValueError("Model must have at least one primary key column.")
        return pk_columns

    def _is_single_pk(self) -> bool:
        """단일 기본 키인지 확인합니다.

        Returns:
            bool: 단일 기본 키이면 True, 복합 기본 키이면 False
        """
        return len(self._get_pk_columns()) == 1

    @classmethod
    def _set_where(cls, stmt: Select, where: list[ColumnElement] | None) -> Select:
        if where is not None and len(where) > 0:
            stmt = stmt.where(*where)
        return stmt

    def _get_model(self) -> type[MODEL_TYPE]:
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

    def _get_pk_values_from_model(self, model: MODEL_TYPE) -> PrimaryKeyType:
        """모델에서 기본 키 값들을 추출합니다.

        단일 PK인 경우 값만 반환하고, 복합키인 경우 딕셔너리로 반환합니다.

        Args:
            model (MODEL_TYPE): 기본 키 값을 추출할 모델 인스턴스

        Returns:
            PrimaryKeyType: 단일 키의 경우 값, 복합키의 경우 딕셔너리
        """
        pk_columns = self._get_pk_columns()

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
    def _has_all_pk_values(cls, pk_values: PrimaryKeyType) -> bool:
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

    def _build_pk_condition(self, pk_value: PrimaryKeyType) -> ColumnElement:
        """기본 키 조건을 생성합니다.

        단일키와 복합키를 모두 지원합니다.

        Args:
            pk_value (PrimaryKeyType): 단일 PK는 값만, 복합키는 딕셔너리 {"col1": val1, "col2": val2}

        Returns:
            ColumnElement: WHERE 절에 사용할 수 있는 조건 요소

        Raises:
            ValueError: 단일 키에 딕셔너리를 전달하거나, 복합키에 누락된 컬럼이 있는 경우
        """
        pk_columns = self._get_pk_columns()

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

    def _build_unique_selectinload_options(
        self, model_cls: type[DeclarativeMeta], visited: set[type[DeclarativeMeta]] = None
    ) -> list[_AbstractLoad]:
        """
        재귀적으로 관계를 따라가며 selectinload 로딩 옵션을 생성하되,
        이미 방문한 모델은 제외한다.

        :param model_cls: SQLAlchemy Declarative 모델 클래스
        :param visited: 이미 방문한 모델 클래스 집합
        :return: SQLAlchemy Load 옵션 리스트 (selectinload(...))
        """
        if visited is None:
            visited = set()

        if model_cls in visited:
            return []

        visited.add(model_cls)

        options: list[_AbstractLoad] = []
        mapper = inspect(model_cls)

        for rel in mapper.relationships:
            attr: InstrumentedAttribute = getattr(model_cls, rel.key)
            target_cls: type[DeclarativeMeta] = rel.mapper.class_

            suboptions = self._build_unique_selectinload_options(
                model_cls=target_cls,
                visited=visited.copy(),  # 복사해서 하위에서 중복 방지 유지
            )

            loader = selectinload(attr)
            if suboptions:
                loader = loader.options(*suboptions)

            options.append(loader)

        return options

    def _build_unique_join_options(
        self, model_cls: type[DeclarativeMeta], visited: set[type[DeclarativeMeta]] = None
    ) -> list[type[DeclarativeMeta]]:
        """
        재귀적으로 관계를 따라가며 join할 테이블들을 수집하되,
        이미 방문한 모델은 제외하고 더 이상 연관관계가 없을 때까지 모든 관계를 탐색한다.

        :param model_cls: SQLAlchemy Declarative 모델 클래스
        :param visited: 이미 방문한 모델 클래스 집합
        :return: join할 모델 클래스 리스트
        """
        if visited is None:
            visited = set()

        if model_cls in visited:
            return []

        visited.add(model_cls)
        join_tables: list[type[DeclarativeMeta]] = []
        mapper = inspect(model_cls)

        for rel in mapper.relationships:
            target_cls: type[DeclarativeMeta] = rel.mapper.class_

            # 현재 관계의 테이블을 join 목록에 추가
            if target_cls not in visited:
                join_tables.append(target_cls)

                # 재귀적으로 하위 관계들도 탐색 (더 이상 연관관계가 없을 때까지)
                sub_joins = self._build_unique_join_options(
                    model_cls=target_cls,
                    visited=visited.copy(),  # 복사해서 하위에서 중복 방지 유지
                )
                join_tables.extend(sub_joins)

        return join_tables

    def _build_join_select_query(
        self, additional_joins: list[type[DeclarativeMeta]] = None, auto_join: bool = False
    ) -> Select[tuple[MODEL_TYPE]]:
        """
        join이 포함된 select 쿼리를 생성합니다.

        Args:
            additional_joins (list[type[DeclarativeMeta]] | None): 추가로 join할 모델 클래스 목록
            auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)

        Returns:
            Select[tuple[MODEL_TYPE]]: join이 포함된 SQLAlchemy select 쿼리 객체
        """
        model_type: type[MODEL_TYPE] = self._get_model()
        stmt = select(model_type)

        join_tables: list[type[DeclarativeMeta]] = []

        if auto_join:
            # 자동으로 관계가 있는 모든 테이블들을 수집 (더 이상 연관관계가 없을 때까지)
            join_tables.extend(self._build_unique_join_options(model_cls=model_type))

        if additional_joins:
            # 추가 join 테이블들을 추가 (중복 제거)
            for join_table in additional_joins:
                if join_table not in join_tables:
                    join_tables.append(join_table)

        # 실제 join 적용
        for join_table in join_tables:
            try:
                stmt = stmt.join(join_table)
            except Exception as e:
                # join이 불가능한 경우 (관계가 없는 경우) 로그를 남기고 스킵
                self.logger.warning(f"Cannot join {join_table.__name__} to {model_type.__name__}: {str(e)}")
                continue

        return stmt

    def _get_select_query(
        self,
        *,
        joins: list[type[DeclarativeMeta]] | None = None,
        auto_join: bool = True,
        use_selectinload: bool = True,
    ) -> Select[tuple[MODEL_TYPE]]:
        """현재 모델에 대한 select 쿼리를 생성합니다.

        Args:
            joins (list[type[DeclarativeMeta]] | None): 명시적으로 join할 모델 클래스 목록
            auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)
            use_selectinload (bool): selectinload 옵션을 사용할지 여부 (기본값: True)

        Returns:
            Select[tuple[MODEL_TYPE]]: SQLAlchemy select 쿼리 객체
        """
        # join 옵션이 있으면 join 쿼리를 사용, 없으면 selectinload 쿼리를 사용
        if joins or auto_join:
            return self._build_join_select_query(additional_joins=joins, auto_join=auto_join)
        else:
            model_type: MODEL_TYPE = self._get_model()
            if use_selectinload:
                options: list[_AbstractLoad] = self._build_unique_selectinload_options(model_type)
                return select(model_type).options(*options)
            else:
                return select(model_type)


class BaseCRUDRepository(Generic[MODEL_TYPE], ISessionRepository, RepositoryUtil):
    def __init_subclass__(cls):
        """서브클래스 생성시 model을 클래스 변수로 설정합니다."""
        super().__init_subclass__()
        cls._model = cls.__extract_model_from_generic()

    def __init__(self):
        self.logger = get_logger()

    # def __getattribute__(self, name: str) -> object:
    #     """
    #     메서드 호출 시점에 환경을 확인하여 적절한 구현을 반환합니다.
    #     """
    #     # Settings가 초기화된 이후, 즉 런타임에만 호출됩니다.
    #     is_async = get_settings().is_async_env
    #
    #     # 공용 메서드 이름과 실제 구현 이름 매핑
    #     method_map = {
    #         "find_by_id": "_find_by_id_async" if is_async else "_find_by_id_sync",
    #         "find": "_find_async" if is_async else "_find_sync",
    #         "find_all": "_find_all_async" if is_async else "_find_all_sync",
    #         "save": "_save_async" if is_async else "_save_sync",
    #         "delete": "_delete_async" if is_async else "_delete_sync",
    #         "exists": "_exists_async" if is_async else "_exists_sync",
    #         "exists_by_id": "_exists_by_id_async" if is_async else "_exists_by_id_sync",
    #         "count": "_count_async" if is_async else "_count_sync",
    #     }
    #
    #     if name in method_map:
    #         # `find_by_id`를 호출하면, 매핑된 `_find_by_id_async` 또는 `_find_by_id_sync`를 반환
    #         internal_method_name = method_map[name]
    #         return super().__getattribute__(internal_method_name)
    #
    #     # 매핑에 없는 속성은 기본 동작을 따름
    #     return super().__getattribute__(name)

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
        return None

    if HAS_ASYNC_SUPPORT:
        from sqlalchemy.ext.asyncio.session import AsyncSession

        @transactional(read_only=True)
        async def find_by_id(
            self,
            id: PrimaryKeyType,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: AsyncSession = None,
        ) -> MODEL_TYPE | None:
            """단일 키 또는 복합키로 모델을 조회합니다.

            Args:
                id (PrimaryKeyType): 단일 키값 또는 복합키 딕셔너리 {"col1": val1, "col2": val2}
                where (list[ColumnElement] | None): 추가 조건
                joins (list[type[DeclarativeMeta]] | None): 명시적으로 join할 모델 클래스 목록
                auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)
                use_selectinload (bool): selectinload 옵션을 사용할지 여부 (기본값: True)
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                MODEL_TYPE | None: 조회된 모델 인스턴스 또는 None
            """
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload).where(
                self._build_pk_condition(id)
            )
            stmt = self._set_where(stmt, where)
            query_result: Result = await session.execute(stmt)
            return query_result.scalar_one_or_none()

        async def find(
            self,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: AsyncSession = None,
        ) -> MODEL_TYPE | None:
            """조건에 맞는 단일 모델을 반환합니다.

            Args:
                where (list[ColumnElement] | None): 조건을 추가할 수 있는 ColumnElement
                joins (list[type[DeclarativeMeta]] | None): 명시적으로 join할 모델 클래스 목록
                auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)
                use_selectinload (bool): selectinload 옵션을 사용할지 여부 (기본값: True)
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                MODEL_TYPE | None: 조건에 맞는 단일 모델 인스턴스 또는 None
            """
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload)
            if where is None:
                self.logger.warning("Where condition is None, returning all models.")
            stmt = self._set_where(stmt, where)
            query_result: Result = await session.execute(stmt)
            return query_result.scalar_one_or_none()

        async def find_all(
            self,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            # pageable: Pageable | None = None,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: AsyncSession = None,
        ) -> list[MODEL_TYPE]:
            """
            조건에 맞는 모든 모델을 조회합니다.

            Args:
                pageable (Pageable | None): 페이징 정보
                where (list[ColumnElement] | None): 조건을 추가할 수 있는 ColumnElement
                joins (list[type[DeclarativeMeta]] | None): 명시적으로 join할 모델 클래스 목록
                auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)
                use_selectinload (bool): selectinload 옵션을 사용할지 여부 (기본값: True)
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                list[MODEL_TYPE]: 조건에 맞는 모델 인스턴스 목록
            """
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload)
            stmt = self._set_where(stmt, where)
            # if pageable:
            #     stmt = stmt.offset(pageable.offset).limit(pageable.limit)
            query_result: Result = await session.execute(stmt)
            return list(query_result.scalars().all())

        async def find_all_by_id(
            self,
            ids: list[PrimaryKeyType],
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: AsyncSession = None,
        ) -> list[MODEL_TYPE]:
            """여러 개의 키로 모델들을 조회합니다.

            Args:
                ids (list[PrimaryKeyType]): 조회할 키 목록 (단일키 또는 복합키 지원)
                where (list[ColumnElement] | None): 추가 조건
                joins (list[type[DeclarativeMeta]] | None): 명시적으로 join할 모델 클래스 목록
                auto_join (bool): 자동으로 관계가 있는 모든 테이블을 join할지 여부 (기본값: False)
                use_selectinload (bool): selectinload 옵션을 사용할지 여부 (기본값: True)
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                list[MODEL_TYPE]: 조회된 모델 인스턴스 목록
            """
            if not ids:
                return []

            conditions: list[ColumnElement] = [self._build_pk_condition(pk_id) for pk_id in ids]
            if where:
                conditions.extend(where)
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload).where(
                or_(*conditions)
            )
            query_result: Result = await session.execute(stmt)
            return list(query_result.scalars().all())

        async def save(self, model: MODEL_TYPE, *, session: AsyncSession = None) -> MODEL_TYPE:
            """모델을 저장합니다.

            단일키와 복합키를 모두 지원하며, 기존 데이터가 있으면 업데이트,
            없으면 삽입됩니다.

            Args:
                model (MODEL_TYPE): 저장할 모델 인스턴스
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                MODEL_TYPE: 저장된 모델 인스턴스
            """
            pk_values = self._get_pk_values_from_model(model)

            if self._has_all_pk_values(pk_values):
                # 모델에 pk 값이 존재
                is_exists: bool = await self.exists_by_id(pk_values, session=session)
                if is_exists:
                    # DB에도 존재하는 경우
                    merged_model = await session.merge(model)
                    await session.flush([merged_model])
                    await session.refresh(merged_model)
                    # save 후 eager load를 위함
                    return await self.find_by_id(self._get_pk_values_from_model(merged_model), session=session)

            session.add(model)
            await session.flush()
            await session.refresh(model)
            # save 후 eager load를 위함
            return await self.find_by_id(self._get_pk_values_from_model(model), session=session)

        async def exists(self, where: list[ColumnElement] | None = None, *, session: AsyncSession = None) -> bool:
            """조건에 맞는 모델이 존재하는지 확인합니다.

            Args:
                where (list[ColumnElement] | None): 조건을 추가할 수 있는 ColumnElement
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                bool: 조건에 맞는 모델이 존재하면 True, 그렇지 않으면 False
            """
            stmt = select(exists().where(*where)) if where else select(exists().select_from(self._get_model()))
            query_result: Result = await session.execute(stmt)
            return query_result.scalar()

        async def exists_by_id(
            self, id: PrimaryKeyType, where: list[ColumnElement] | None = None, *, session: AsyncSession
        ) -> bool:
            """단일 키 또는 복합키로 모델이 존재하는지 확인합니다.

            Args:
                id (PrimaryKeyType): 단일 키값 또는 복합키 딕셔너리
                where (list[ColumnElement] | None): 추가 조건
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                bool: 모델이 존재하면 True, 그렇지 않으면 False
            """
            pk_condition = self._build_pk_condition(id)
            stmt = select(exists().where(pk_condition))
            stmt = self._set_where(stmt, where)
            query_result: Result = await session.execute(stmt)
            return query_result.scalar()

        async def count(self, where: list[ColumnElement] | None = None, *, session: AsyncSession = None) -> int:
            """모델의 총 개수를 반환합니다.

            Args:
                where (ColumnElement | None): 조건을 추가할 수 있는 ColumnElement
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                int: 모델의 총 개수
            """
            pk_columns = self._get_pk_columns()
            # 첫 번째 pk 컬럼을 사용해서 count
            stmt = select(func.count(pk_columns[0].distinct())).select_from(self._get_model())
            stmt = self._set_where(stmt, where)
            return await session.scalar(stmt)

        async def delete(
            self, model: MODEL_TYPE, where: list[ColumnElement] | None = None, *, session: AsyncSession
        ) -> bool:
            """모델을 삭제합니다.

            Args:
                model (MODEL_TYPE): 삭제할 모델 인스턴스
                where (list[ColumnElement] | None): 추가 조건
                session (AsyncSession): SQLAlchemy AsyncSession 인스턴스

            Returns:
                bool: 삭제 성공 시 True, 삭제할 모델이 없으면 False
            """
            pk_values = self._get_pk_values_from_model(model)
            saved_model: MODEL_TYPE = await self.find_by_id(pk_values, where=where, session=session)

            if saved_model is None:
                return False

            await session.delete(saved_model)
            await session.flush()
            return True

    else:

        def find_by_id(
            self,
            id: PrimaryKeyType,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: Session,
        ) -> MODEL_TYPE | None:
            """단일 키 또는 복합키로 모델을 조회합니다."""
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload).where(
                self._build_pk_condition(id)
            )
            stmt = self._set_where(stmt, where)
            query_result: Result = session.execute(stmt)
            return query_result.scalar_one_or_none()

        def find(
            self,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: Session,
        ) -> MODEL_TYPE | None:
            """조건에 맞는 단일 모델을 반환합니다."""
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload)
            stmt = self._set_where(stmt, where)
            query_result: Result = session.execute(stmt)
            return query_result.scalar_one_or_none()

        def find_all(
            self,
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            # pageable: Pageable | None = None,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: Session,
        ) -> list[MODEL_TYPE]:
            """조건에 맞는 모든 모델을 조회합니다."""
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload)
            stmt = self._set_where(stmt, where)
            # TODO 2025-08-22 00:17:25 : 이거 어떻게 할지 생각해봐야 함
            # if pageable:
            #     stmt = stmt.offset(pageable.offset).limit(pageable.limit)
            query_result: Result = session.execute(stmt)
            return list(query_result.scalars().all())

        def find_all_by_id(
            self,
            ids: list[PrimaryKeyType],
            where: list[ColumnElement] | None = None,
            joins: list[type[DeclarativeMeta]] | None = None,
            *,
            auto_join: bool = True,
            use_selectinload: bool = True,
            session: Session,
        ) -> list[MODEL_TYPE]:
            """여러 개의 키로 모델들을 조회합니다."""
            if not ids:
                return []

            conditions: list[ColumnElement] = [self._build_pk_condition(pk_id) for pk_id in ids]
            if where:
                conditions.extend(where)
            stmt = self._get_select_query(joins=joins, auto_join=auto_join, use_selectinload=use_selectinload).where(
                or_(*conditions)
            )
            query_result: Result = session.execute(stmt)
            return list(query_result.scalars().all())

        def save(self, model: MODEL_TYPE, *, session: Session) -> MODEL_TYPE:
            """모델을 저장합니다."""
            pk_values = self._get_pk_values_from_model(model)

            if self._has_all_pk_values(pk_values):
                is_exists: bool = self.exists_by_id(pk_values, session=session)
                if is_exists:
                    merged_model = session.merge(model)
                    session.flush([merged_model])
                    session.refresh(merged_model)
                    return self.find_by_id(self._get_pk_values_from_model(merged_model), session=session)

            session.add(model)
            session.flush()
            session.refresh(model)
            return self.find_by_id(self._get_pk_values_from_model(model), session=session)

        def exists(self, where: list[ColumnElement] | None = None, *, session: Session) -> bool:
            """조건에 맞는 모델이 존재하는지 확인합니다."""
            stmt = select(exists().where(*where)) if where else select(exists().select_from(self._get_model()))
            query_result: Result = session.execute(stmt)
            return query_result.scalar()

        def exists_by_id(
            self, id: PrimaryKeyType, where: list[ColumnElement] | None = None, *, session: Session
        ) -> bool:
            """단일 키 또는 복합키로 모델이 존재하는지 확인합니다."""
            pk_condition = self._build_pk_condition(id)
            stmt = select(exists().where(pk_condition))
            stmt = self._set_where(stmt, where)
            query_result: Result = session.execute(stmt)
            return query_result.scalar()

        def count(self, where: list[ColumnElement] | None = None, *, session: Session) -> int:
            """모델의 총 개수를 반환합니다."""
            pk_columns = self._get_pk_columns()
            stmt = select(func.count(pk_columns[0].distinct())).select_from(self._get_model())
            stmt = self._set_where(stmt, where)
            return session.scalar(stmt)

        def delete(self, model: MODEL_TYPE, where: list[ColumnElement] | None = None, *, session: Session) -> bool:
            """모델을 삭제합니다."""
            pk_values = self._get_pk_values_from_model(model)
            saved_model: MODEL_TYPE = self.find_by_id(pk_values, where=where, session=session)

            if saved_model is None:
                return False

            session.delete(saved_model)
            session.flush()
            return True


class BaseCRUDTransactionRepository(BaseCRUDRepository[MODEL_TYPE], ITransactionalRepository): ...
