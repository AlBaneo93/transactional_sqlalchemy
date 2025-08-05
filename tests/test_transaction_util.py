from unittest.mock import Mock, patch

import pytest
from sqlalchemy.ext.asyncio.session import AsyncSession

from transactional_sqlalchemy.utils.transaction_util import (
    add_session_to_context,
    allocate_session_in_args,
    find_orm_instance,
    get_current_transaction_depth,
    get_session_from_context,
    get_session_stack_size,
    has_active_transaction,
    is_orm_instance,
    remove_session_from_context,
    reset_pk_fields,
    with_transaction_context,
)


class TestIsOrmInstance:
    """is_orm_instance 함수 테스트"""

    def test_is_orm_instance_valid_orm_object(self):
        """유효한 ORM 객체인지 테스트"""
        mock_obj = Mock()
        mock_obj.__mapper__ = Mock()
        mock_obj.__class__.__table__ = Mock()

        result = is_orm_instance(mock_obj)
        assert result is True

    def test_is_orm_instance_no_mapper(self):
        """__mapper__ 속성이 없는 객체 테스트"""
        mock_obj = Mock()
        mock_obj.__class__.__table__ = Mock()
        del mock_obj.__mapper__

        result = is_orm_instance(mock_obj)
        assert result is False

    def test_is_orm_instance_no_table(self):
        """__table__ 속성이 없는 객체 테스트"""

        # Mock 클래스 생성 후 __table__ 속성 없이 설정
        class MockObjClass:
            pass

        mock_obj = Mock()
        mock_obj.__mapper__ = Mock()
        mock_obj.__class__ = MockObjClass

        result = is_orm_instance(mock_obj)
        assert result is False

    def test_is_orm_instance_plain_object(self):
        """일반 객체 테스트"""
        obj = {"key": "value"}

        result = is_orm_instance(obj)
        assert result is False


class TestFindOrmInstance:
    """find_orm_instance 함수 테스트"""

    def test_find_orm_instance_single_orm_in_args(self):
        """args에 단일 ORM 인스턴스가 있는 경우"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        result = find_orm_instance(mock_orm, "string", 123)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_multiple_orm_in_args(self):
        """args에 여러 ORM 인스턴스가 있는 경우"""
        mock_orm1 = Mock()
        mock_orm1.__mapper__ = Mock()
        mock_orm1.__class__.__table__ = Mock()

        mock_orm2 = Mock()
        mock_orm2.__mapper__ = Mock()
        mock_orm2.__class__.__table__ = Mock()

        result = find_orm_instance(mock_orm1, mock_orm2, "string")
        assert len(result) == 2
        assert mock_orm1 in result
        assert mock_orm2 in result

    def test_find_orm_instance_orm_in_kwargs(self):
        """kwargs에 ORM 인스턴스가 있는 경우"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        result = find_orm_instance(key1="value1", model=mock_orm)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_orm_in_list(self):
        """리스트 안에 ORM 인스턴스가 있는 경우"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        models_list = [mock_orm, "string", 123]
        result = find_orm_instance(models_list)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_orm_in_tuple(self):
        """튜플 안에 ORM 인스턴스가 있는 경우"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        models_tuple = (mock_orm, "string")
        result = find_orm_instance(models_tuple)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_orm_in_set(self):
        """셋 안에 ORM 인스턴스가 있는 경우"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        models_set = {mock_orm, "string"}
        result = find_orm_instance(models_set)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_nested_collections(self):
        """중첩된 컬렉션에서 ORM 인스턴스 찾기"""
        mock_orm = Mock()
        mock_orm.__mapper__ = Mock()
        mock_orm.__class__.__table__ = Mock()

        nested_list = [["string", mock_orm], 123]
        result = find_orm_instance(nested_list)
        assert len(result) == 1
        assert result[0] is mock_orm

    def test_find_orm_instance_exclude_string_dict(self):
        """문자열과 딕셔너리는 제외되는지 테스트"""
        result = find_orm_instance("string", {"key": "value"}, b"bytes")
        assert len(result) == 0

    def test_find_orm_instance_no_orm_objects(self):
        """ORM 객체가 없는 경우"""
        result = find_orm_instance("string", 123, ["list"], {"dict": "value"})
        assert len(result) == 0


class TestResetPkFields:
    """reset_pk_fields 함수 테스트"""

    def test_reset_pk_fields_single_model(self):
        """단일 모델의 PK 필드 리셋 테스트"""
        mock_model = Mock()
        mock_column = Mock()
        mock_column.key = "id"
        mock_mapper = Mock()
        mock_mapper.primary_key = [mock_column]
        mock_model.__mapper__ = mock_mapper

        reset_pk_fields(mock_model)

        # id 속성이 None으로 설정되었는지 확인
        assert mock_model.id is None

    def test_reset_pk_fields_list_of_models(self):
        """모델 리스트의 PK 필드 리셋 테스트"""
        mock_model1 = Mock()
        mock_model2 = Mock()

        mock_column1 = Mock()
        mock_column1.key = "id"
        mock_mapper1 = Mock()
        mock_mapper1.primary_key = [mock_column1]
        mock_model1.__mapper__ = mock_mapper1

        mock_column2 = Mock()
        mock_column2.key = "user_id"
        mock_mapper2 = Mock()
        mock_mapper2.primary_key = [mock_column2]
        mock_model2.__mapper__ = mock_mapper2

        models_list = [mock_model1, mock_model2]
        reset_pk_fields(models_list)

        # 각 모델의 PK가 None으로 설정되었는지 확인
        assert mock_model1.id is None
        assert mock_model2.user_id is None

    def test_reset_pk_fields_tuple_of_models(self):
        """모델 튜플의 PK 필드 리셋 테스트"""
        mock_model = Mock()
        mock_column = Mock()
        mock_column.key = "id"
        mock_mapper = Mock()
        mock_mapper.primary_key = [mock_column]
        mock_model.__mapper__ = mock_mapper

        models_tuple = (mock_model,)
        reset_pk_fields(models_tuple)

        assert mock_model.id is None

    def test_reset_pk_fields_set_of_models(self):
        """모델 셋의 PK 필드 리셋 테스트"""
        mock_model = Mock()
        mock_column = Mock()
        mock_column.key = "id"
        mock_mapper = Mock()
        mock_mapper.primary_key = [mock_column]
        mock_model.__mapper__ = mock_mapper

        models_set = {mock_model}
        reset_pk_fields(models_set)

        assert mock_model.id is None


class TestSessionContextFunctions:
    """세션 컨텍스트 관련 함수들 테스트"""

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_add_session_to_context_valid_session(self, mock_context):
        """유효한 세션을 컨텍스트에 추가하는 테스트"""
        mock_stack = Mock()
        mock_context.get.return_value = mock_stack
        mock_session = Mock(spec=AsyncSession)

        add_session_to_context(mock_session)

        mock_stack.push.assert_called_once_with(mock_session)

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_add_session_to_context_none_session(self, mock_context):
        """None 세션을 컨텍스트에 추가할 때 예외 발생 테스트"""
        with pytest.raises(ValueError, match="세션이 None입니다"):
            add_session_to_context(None)

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_get_session_from_context_with_session(self, mock_context):
        """컨텍스트에서 세션을 가져오는 테스트 (세션 존재)"""
        mock_stack = Mock()
        mock_stack.size.return_value = 1
        mock_session = Mock()
        mock_stack.peek.return_value = mock_session
        mock_context.get.return_value = mock_stack

        result = get_session_from_context()

        assert result is mock_session

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_get_session_from_context_empty_stack(self, mock_context):
        """컨텍스트에서 세션을 가져오는 테스트 (빈 스택)"""
        mock_stack = Mock()
        mock_stack.size.return_value = 0
        mock_context.get.return_value = mock_stack

        result = get_session_from_context()

        assert result is None

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_remove_session_from_context_with_session(self, mock_context):
        """컨텍스트에서 세션을 제거하는 테스트 (세션 존재)"""
        mock_stack = Mock()
        mock_stack.size.return_value = 1
        mock_context.get.return_value = mock_stack

        remove_session_from_context()

        mock_stack.pop.assert_called_once()

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_remove_session_from_context_empty_stack(self, mock_context):
        """컨텍스트에서 세션을 제거하는 테스트 (빈 스택)"""
        mock_stack = Mock()
        mock_stack.size.return_value = 0
        mock_context.get.return_value = mock_stack

        with pytest.raises(ValueError, match="트랜잭션 컨텍스트에 세션이 없습니다"):
            remove_session_from_context()

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_remove_session_from_context_stack_becomes_empty(self, mock_context):
        """세션 제거 후 스택이 비게 되는 경우 테스트"""
        mock_stack = Mock()
        mock_stack.size.side_effect = [1, 0]  # 첫 번째는 1, 두 번째는 0
        mock_context.get.return_value = mock_stack

        remove_session_from_context()

        mock_stack.pop.assert_called_once()
        # 스택이 비었을 때 새로운 스택으로 초기화
        mock_context.set.assert_called_once()

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_get_session_stack_size(self, mock_context):
        """세션 스택 크기 반환 테스트"""
        mock_stack = Mock()
        mock_stack.size.return_value = 3
        mock_context.get.return_value = mock_stack

        result = get_session_stack_size()

        assert result == 3

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_get_session_stack_size_none_stack(self, mock_context):
        """스택이 None인 경우 테스트"""
        mock_context.get.return_value = None

        result = get_session_stack_size()

        assert result == 0

    @patch("transactional_sqlalchemy.utils.transaction_util.get_session_stack_size")
    def test_has_active_transaction_true(self, mock_stack_size):
        """활성 트랜잭션이 있는 경우 테스트"""
        mock_stack_size.return_value = 2

        result = has_active_transaction()

        assert result is True

    @patch("transactional_sqlalchemy.utils.transaction_util.get_session_stack_size")
    def test_has_active_transaction_false(self, mock_stack_size):
        """활성 트랜잭션이 없는 경우 테스트"""
        mock_stack_size.return_value = 0

        result = has_active_transaction()

        assert result is False

    @patch("transactional_sqlalchemy.utils.transaction_util.get_session_stack_size")
    def test_get_current_transaction_depth(self, mock_stack_size):
        """현재 트랜잭션 깊이 반환 테스트"""
        mock_stack_size.return_value = 5

        result = get_current_transaction_depth()

        assert result == 5


class TestAllocateSessionInArgs:
    """allocate_session_in_args 함수 테스트"""

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    @patch("transactional_sqlalchemy.utils.transaction_util.SessionHandler")
    def test_allocate_session_new_session_empty_stack(self, mock_handler_class, mock_context):
        """빈 스택에서 새 세션 할당 테스트"""
        # Mock setup
        mock_stack = Mock()
        mock_stack.size.return_value = 0
        mock_context.get.return_value = mock_stack

        mock_session = Mock()
        mock_manager = Mock()
        mock_manager.get_new_session.return_value = (mock_session, Mock())

        mock_handler = Mock()
        mock_handler.get_manager.return_value = mock_manager
        mock_handler_class.return_value = mock_handler

        # BoundArguments mock
        from inspect import BoundArguments

        mock_bound_args = Mock(spec=BoundArguments)
        mock_bound_args.arguments = {"session": None}

        allocate_session_in_args(mock_bound_args)

        mock_stack.push.assert_called_once_with(mock_session)
        assert mock_bound_args.arguments["session"] is mock_session

    @patch("transactional_sqlalchemy.utils.transaction_util.transaction_context")
    def test_allocate_session_existing_session_in_stack(self, mock_context):
        """스택에 기존 세션이 있는 경우 테스트"""
        mock_stack = Mock()
        mock_stack.size.return_value = 1
        mock_existing_session = Mock()
        mock_stack.peek.return_value = mock_existing_session
        mock_context.get.return_value = mock_stack

        from inspect import BoundArguments

        mock_bound_args = Mock(spec=BoundArguments)
        mock_bound_args.arguments = {"session": None}

        allocate_session_in_args(mock_bound_args)

        assert mock_bound_args.arguments["session"] is mock_existing_session

    def test_allocate_session_no_session_argument(self):
        """session 인자가 없는 경우 테스트"""
        from inspect import BoundArguments

        mock_bound_args = Mock(spec=BoundArguments)
        mock_bound_args.arguments = {"other_arg": "value"}

        # 예외 없이 실행되어야 함
        allocate_session_in_args(mock_bound_args)

    # 복잡한 SessionHandler 초기화가 필요한 테스트는 통합 테스트에서 다룹니다.


class TestWithTransactionContext:
    """with_transaction_context 데코레이터 테스트"""

    @patch("transactional_sqlalchemy.utils.transaction_util.iscoroutinefunction")
    @patch("transactional_sqlalchemy.utils.transaction_util.unwrap")
    def test_with_transaction_context_sync_function(self, mock_unwrap, mock_is_coroutine):
        """동기 함수에 데코레이터 적용 테스트"""
        mock_is_coroutine.return_value = False

        def sample_func(arg1, session=None):
            return f"result_{arg1}"

        mock_unwrap.return_value = sample_func

        decorated = with_transaction_context(sample_func)

        assert callable(decorated)

    @patch("transactional_sqlalchemy.utils.transaction_util.iscoroutinefunction")
    @patch("transactional_sqlalchemy.utils.transaction_util.unwrap")
    def test_with_transaction_context_async_function(self, mock_unwrap, mock_is_coroutine):
        """비동기 함수에 데코레이터 적용 테스트"""
        mock_is_coroutine.return_value = True

        async def sample_async_func(arg1, session=None):
            return f"async_result_{arg1}"

        mock_unwrap.return_value = sample_async_func

        decorated = with_transaction_context(sample_async_func)

        assert callable(decorated)
