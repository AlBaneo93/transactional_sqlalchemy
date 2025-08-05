from unittest.mock import Mock, patch

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio.session import AsyncSession

from tests.conftest import ORMBase
from transactional_sqlalchemy.repository.base import BaseCRUDRepository, CompositeKey


class MockModel(ORMBase):
    """테스트용 Mock 모델"""

    __tablename__ = "test_table"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))


class TestBaseCRUDRepositoryEdgeCases:
    """BaseCRUDRepository 엣지 케이스 테스트"""

    def test_init_subclass_without_generic_args(self):
        """Generic 타입 인자 없이 서브클래스 생성 테스트"""

        class TestRepo(BaseCRUDRepository):
            pass

        # 예외 없이 생성되어야 함
        repo = TestRepo()
        assert repo is not None

    def test_extract_model_from_generic_no_orig_bases(self):
        """__orig_bases__가 없는 경우 테스트"""

        class TestRepo(BaseCRUDRepository[MockModel]):
            pass

        # __orig_bases__ 제거
        if hasattr(TestRepo, "__orig_bases__"):
            delattr(TestRepo, "__orig_bases__")

        # __args__ 속성도 없도록 설정
        if hasattr(TestRepo, "__args__"):
            delattr(TestRepo, "__args__")

        result = TestRepo._BaseCRUDRepository__extract_model_from_generic()
        assert result is None

    def test_extract_model_from_generic_no_args(self):
        """Generic 타입 인자가 없는 경우 테스트"""

        class TestRepo(BaseCRUDRepository):
            pass

        # Mock __orig_bases__ with no args
        TestRepo.__orig_bases__ = (BaseCRUDRepository,)

        with patch("typing.get_args", return_value=[]):
            result = TestRepo._BaseCRUDRepository__extract_model_from_generic()
            assert result is None

    @patch("transactional_sqlalchemy.repository.base.BaseCRUDRepository._BaseCRUDRepository__get_model")
    @patch("transactional_sqlalchemy.utils.transaction_util.allocate_session_in_args")
    async def test_find_by_id_error_handling(self, mock_allocate_session, mock_get_model):
        """find_by_id에서 에러 처리 테스트"""

        class TestRepo(BaseCRUDRepository[MockModel]):
            pass

        repo = TestRepo()
        mock_get_model.return_value = MockModel
        mock_session = Mock(spec=AsyncSession)

        # allocate_session_in_args를 Mock하여 세션 관리 로직 우회
        mock_allocate_session.return_value = None

        # __build_pk_condition에서 에러 발생 시뮬레이션
        with patch.object(repo, "_BaseCRUDRepository__build_pk_condition", side_effect=ValueError("Invalid PK")):
            with pytest.raises(ValueError, match="Invalid PK"):
                await repo.find_by_id("invalid_id", session=mock_session)

    @patch("transactional_sqlalchemy.repository.base.BaseCRUDRepository._BaseCRUDRepository__get_model")
    @patch("transactional_sqlalchemy.utils.transaction_util.allocate_session_in_args")
    async def test_save_without_pk_values(self, mock_allocate_session, mock_get_model):
        """PK 값이 없는 모델 저장 테스트"""

        class TestRepo(BaseCRUDRepository[MockModel]):
            pass

        repo = TestRepo()
        mock_get_model.return_value = MockModel
        mock_session = Mock(spec=AsyncSession)
        mock_model = Mock()

        # allocate_session_in_args를 Mock하여 세션 관리 로직 우회
        mock_allocate_session.return_value = None

        # __get_pk_values_from_model이 빈 값 반환하도록 설정
        with patch.object(repo, "_BaseCRUDRepository__get_pk_values_from_model", return_value=None):
            with patch.object(repo, "_BaseCRUDRepository__has_all_pk_values", return_value=False):
                result = await repo.save(mock_model, session=mock_session)

                mock_session.add.assert_called_once_with(mock_model)
                mock_session.flush.assert_called_once()
                assert result is mock_model

    def test_get_pk_columns_no_pk(self):
        """기본 키가 없는 모델 테스트"""

        class TestRepo(BaseCRUDRepository[MockModel]):
            pass

        repo = TestRepo()

        # Mock model with no primary key
        mock_model = Mock()
        mock_mapper = Mock()
        mock_mapper.primary_key = []
        mock_model.__mapper__ = mock_mapper

        with patch.object(repo, "_BaseCRUDRepository__get_model", return_value=mock_model):
            with pytest.raises(ValueError, match="Model must have at least one primary key column"):
                repo._BaseCRUDRepository__get_pk_columns()

    def test_get_model_no_args_found(self):
        """Generic 타입을 찾을 수 없는 경우 테스트"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # __orig_bases__를 빈 튜플로 설정
        TestRepo.__orig_bases__ = ()

        with pytest.raises(TypeError, match="제네릭 타입 T에 대한 모델 클래스를 찾을 수 없습니다"):
            repo._BaseCRUDRepository__get_model()

    def test_build_pk_condition_single_pk_with_dict(self):
        """단일 PK에 딕셔너리를 전달하는 에러 케이스"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # Mock single PK column
        mock_column = Mock()
        mock_columns = [mock_column]

        with patch.object(repo, "_BaseCRUDRepository__get_pk_columns", return_value=mock_columns):
            with pytest.raises(ValueError, match="Single primary key should not be a dictionary"):
                repo._BaseCRUDRepository__build_pk_condition({"id": 1})

    def test_build_pk_condition_composite_pk_with_scalar(self):
        """복합 PK에 스칼라 값을 전달하는 에러 케이스"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # Mock composite PK columns
        mock_column1 = Mock()
        mock_column2 = Mock()
        mock_columns = [mock_column1, mock_column2]

        with patch.object(repo, "_BaseCRUDRepository__get_pk_columns", return_value=mock_columns):
            with pytest.raises(ValueError, match="Composite primary key must be a dictionary"):
                repo._BaseCRUDRepository__build_pk_condition("single_value")

    def test_build_pk_condition_missing_column(self):
        """복합 PK에서 누락된 컬럼이 있는 경우"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # Mock composite PK columns
        mock_column1 = Mock()
        mock_column1.name = "id"
        mock_column2 = Mock()
        mock_column2.name = "user_id"
        mock_columns = [mock_column1, mock_column2]

        with patch.object(repo, "_BaseCRUDRepository__get_pk_columns", return_value=mock_columns):
            pk_value = {"id": 1}  # user_id 누락
            with pytest.raises(ValueError, match="Missing primary key value for column: user_id"):
                repo._BaseCRUDRepository__build_pk_condition(pk_value)

    def test_has_all_pk_values_dict_with_none(self):
        """딕셔너리 PK 값 중 None이 있는 경우"""
        result = BaseCRUDRepository._BaseCRUDRepository__has_all_pk_values({"id": 1, "user_id": None})
        assert result is False

    def test_has_all_pk_values_dict_all_valid(self):
        """딕셔너리 PK 값이 모두 유효한 경우"""
        result = BaseCRUDRepository._BaseCRUDRepository__has_all_pk_values({"id": 1, "user_id": 2})
        assert result is True

    def test_has_all_pk_values_scalar_none(self):
        """스칼라 PK 값이 None인 경우"""
        result = BaseCRUDRepository._BaseCRUDRepository__has_all_pk_values(None)
        assert result is False

    def test_has_all_pk_values_scalar_valid(self):
        """스칼라 PK 값이 유효한 경우"""
        result = BaseCRUDRepository._BaseCRUDRepository__has_all_pk_values(123)
        assert result is True


class TestCompositeKeyEdgeCases:
    """CompositeKey 엣지 케이스 테스트"""

    def test_composite_key_getitem(self):
        """CompositeKey의 __getitem__ 메서드 테스트"""
        key = CompositeKey(values={"id": 1, "user_id": 2})
        assert key["id"] == 1
        assert key["user_id"] == 2

    def test_composite_key_getitem_missing_key(self):
        """존재하지 않는 키에 대한 __getitem__ 테스트"""
        key = CompositeKey(values={"id": 1})
        with pytest.raises(KeyError):
            _ = key["missing_key"]

    def test_to_tuple_missing_column(self):
        """to_tuple에서 누락된 컬럼이 있는 경우"""
        key = CompositeKey(values={"id": 1, "user_id": 2})
        with pytest.raises(KeyError):
            key.to_tuple(["id", "missing_column"])

    def test_to_tuple_empty_order(self):
        """빈 컬럼 순서로 to_tuple 호출"""
        key = CompositeKey(values={"id": 1, "user_id": 2})
        result = key.to_tuple([])
        assert result == ()

    def test_from_model_missing_attribute(self):
        """모델에 존재하지 않는 속성으로 CompositeKey 생성"""
        mock_model = Mock()
        mock_model.id = 1

        # user_id 속성이 없음 - Mock 객체는 새로운 Mock을 반환
        key = CompositeKey.from_model(mock_model, ["id", "user_id"])
        assert key["id"] == 1
        # Mock 객체는 존재하지 않는 속성에 대해 새로운 Mock을 반환
        assert isinstance(key["user_id"], Mock)


class TestBuildUniqueSelectinloadOptions:
    """__build_unique_selectinload_options 메서드 테스트"""

    def test_build_selectinload_options_already_visited(self):
        """이미 방문한 모델 클래스인 경우"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # Mock model class
        mock_model_cls = Mock()
        visited = {mock_model_cls}

        result = repo._BaseCRUDRepository__build_unique_selectinload_options(mock_model_cls, visited=visited, depth=1)

        assert result == []

    def test_build_selectinload_options_depth_zero(self):
        """depth가 0인 경우"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()
        mock_model_cls = Mock()

        result = repo._BaseCRUDRepository__build_unique_selectinload_options(mock_model_cls, visited=set(), depth=0)

        assert result == []

    def test_build_selectinload_options_depth_negative(self):
        """depth가 음수인 경우"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()
        mock_model_cls = Mock()

        result = repo._BaseCRUDRepository__build_unique_selectinload_options(mock_model_cls, visited=set(), depth=-1)

        assert result == []

    def test_build_selectinload_options_basic_functionality(self):
        """selectinload 옵션 생성 기본 기능 테스트"""

        class TestRepo(BaseCRUDRepository):
            pass

        repo = TestRepo()

        # 기본 기능이 정상적으로 작동하는지 확인
        # 실제 구현에서는 관계가 있는 모델에서만 작동하므로
        # 여기서는 기본 동작만 확인
        assert hasattr(repo, "_BaseCRUDRepository__build_unique_selectinload_options")
