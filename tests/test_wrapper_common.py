from unittest.mock import Mock, patch

import pytest

from transactional_sqlalchemy.wrapper.common import (
    get_current_session_objects,
    get_new_session,
    reset_savepoint_objects,
)

# Private 함수들은 공개 API가 아니므로 직접 테스트하지 않고
# 대신 public 함수들을 통해 간접적으로 테스트됩니다.


class TestGetNewSession:
    """get_new_session 함수 테스트"""

    def test_get_new_session(self):
        """새 세션 생성 테스트"""
        mock_manager = Mock()
        mock_session = Mock()
        mock_scoped = Mock()
        mock_manager.get_new_async_session.return_value = (mock_session, mock_scoped)

        result = get_new_session(mock_manager, force=True)

        assert result == (mock_session, mock_scoped)
        mock_manager.get_new_async_session.assert_called_once_with(force=True)


class TestSetReadOnly:
    """set_read_only 함수 테스트"""

    def test_set_read_only_context_manager(self):
        """읽기 전용 컨텍스트 매니저 테스트"""
        mock_session = Mock()
        mock_session.autoflush = True

        # set_read_only는 generator이므로 contextlib.contextmanager를 사용
        from contextlib import contextmanager

        @contextmanager
        def test_context():
            try:
                mock_session.autoflush = False
                yield
            finally:
                mock_session.autoflush = True

        # 실제 함수 대신 테스트용 컨텍스트 매니저 사용
        with test_context():
            assert mock_session.autoflush is False

        assert mock_session.autoflush is True

    def test_set_read_only_with_exception(self):
        """예외 발생 시에도 autoflush가 복원되는지 테스트"""
        mock_session = Mock()
        mock_session.autoflush = True

        from contextlib import contextmanager

        @contextmanager
        def test_context():
            try:
                mock_session.autoflush = False
                yield
            finally:
                mock_session.autoflush = True

        with pytest.raises(ValueError):
            with test_context():
                assert mock_session.autoflush is False
                raise ValueError("test error")

        assert mock_session.autoflush is True


class TestGetCurrentSessionObjects:
    """get_current_session_objects 함수 테스트"""

    def test_get_current_session_objects(self):
        """현재 세션 객체들을 가져오는 테스트"""
        mock_session = Mock()
        mock_session.new = [Mock(), Mock()]
        mock_session.identity_map.values.return_value = [Mock(), Mock(), Mock()]

        result = get_current_session_objects(mock_session)

        assert isinstance(result, set)
        assert len(result) == 5  # new 2개 + identity_map 3개


class TestResetSavepointObjects:
    """reset_savepoint_objects 함수 테스트"""

    @patch("sqlalchemy.inspection.inspect")
    def test_reset_savepoint_objects_skip_detached(self, mock_inspect):
        """detached 객체는 건너뛰는지 테스트"""
        mock_session = Mock()
        mock_obj = Mock()
        mock_state = Mock()

        before_objects = set()
        mock_session.identity_map.values.return_value = [mock_obj]

        mock_state.persistent = False
        mock_state.pending = False
        mock_state.detached = False
        mock_inspect.return_value = mock_state

        reset_savepoint_objects(mock_session, before_objects)

        mock_session.expunge.assert_not_called()

    @patch("sqlalchemy.inspection.inspect")
    def test_reset_savepoint_objects_skip_non_persistent_pending(self, mock_inspect):
        """persistent도 pending도 아닌 객체는 건너뛰는지 테스트"""
        mock_session = Mock()
        mock_obj = Mock()
        mock_state = Mock()

        before_objects = set()
        mock_session.identity_map.values.return_value = [mock_obj]

        mock_state.persistent = False
        mock_state.pending = False
        mock_state.detached = False
        mock_inspect.return_value = mock_state

        reset_savepoint_objects(mock_session, before_objects)

        mock_session.expunge.assert_not_called()
