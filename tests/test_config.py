from unittest.mock import Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from sqlalchemy.orm import Session, scoped_session

from transactional_sqlalchemy.config import (
    ScopeAndSessionManager,
    SessionHandler,
    init_manager,
    verify_config,
)


class TestVerifyConfig:
    """verify_config 함수 테스트"""

    def test_verify_config_with_scoped_session(self):
        """scoped_session이 제공된 경우 테스트"""
        mock_scoped_session = Mock()
        # 예외 없이 실행되어야 함
        verify_config(scoped_session=mock_scoped_session)

    def test_verify_config_without_scoped_session(self):
        """scoped_session이 제공되지 않은 경우 테스트"""
        with pytest.raises(ValueError, match="scoped_session is required"):
            verify_config()

    def test_verify_config_with_other_kwargs(self):
        """다른 kwargs와 함께 scoped_session이 제공된 경우 테스트"""
        mock_scoped_session = Mock()
        # 예외 없이 실행되어야 함
        verify_config(scoped_session=mock_scoped_session, other_param="value")


class TestScopeAndSessionManager:
    """ScopeAndSessionManager 클래스 테스트"""

    def setup_method(self):
        """각 테스트 전에 싱글톤 인스턴스 초기화"""
        ScopeAndSessionManager._ScopeAndSessionManager__instance = None

    def test_singleton_pattern(self):
        """싱글톤 패턴이 올바르게 작동하는지 테스트"""
        mock_scoped_session = Mock()

        with patch("transactional_sqlalchemy.config.verify_config"):
            manager1 = ScopeAndSessionManager(mock_scoped_session)
            manager2 = ScopeAndSessionManager(mock_scoped_session)

        assert manager1 is manager2

    @patch("transactional_sqlalchemy.config.verify_config")
    @patch("logging.debug")
    def test_init_calls_verify_config(self, mock_debug, mock_verify):
        """초기화 시 verify_config가 호출되는지 테스트"""
        mock_scoped_session = Mock()

        ScopeAndSessionManager(mock_scoped_session)

        mock_verify.assert_called_once_with(scoped_session=mock_scoped_session)
        mock_debug.assert_called_once()

    def test_get_new_session_force_true(self):
        """force=True일 때 get_new_session 테스트"""
        mock_scoped_session = Mock()
        mock_session = Mock(spec=Session)
        mock_scoped_session.return_value = mock_session

        with patch("transactional_sqlalchemy.config.verify_config"):
            manager = ScopeAndSessionManager(mock_scoped_session)

        result = manager.get_new_session(force=True)

        assert result == (mock_session, mock_scoped_session)
        mock_scoped_session.assert_called_once_with()

    def test_get_new_session_force_false(self):
        """force=False일 때 get_new_session 테스트"""
        mock_scoped_session = Mock()
        mock_session = Mock(spec=Session)
        mock_session_factory = Mock()
        mock_session_factory.return_value = mock_session
        mock_scoped_session.session_factory = mock_session_factory

        with patch("transactional_sqlalchemy.config.verify_config"):
            manager = ScopeAndSessionManager(mock_scoped_session)

        result = manager.get_new_session(force=False)

        assert result == (mock_session, mock_scoped_session)
        mock_session_factory.assert_called_once_with()

    def test_get_new_async_session_force_true(self):
        """force=True일 때 get_new_async_session 테스트"""
        mock_async_scoped_session = Mock()
        mock_async_session = Mock(spec=AsyncSession)
        mock_async_scoped_session.return_value = mock_async_session

        with patch("transactional_sqlalchemy.config.verify_config"):
            manager = ScopeAndSessionManager(mock_async_scoped_session)

        result = manager.get_new_async_session(force=True)

        assert result == (mock_async_session, mock_async_scoped_session)
        mock_async_scoped_session.assert_called_once_with()

    def test_get_new_async_session_force_false(self):
        """force=False일 때 get_new_async_session 테스트"""
        mock_async_scoped_session = Mock()
        mock_async_session = Mock(spec=AsyncSession)
        mock_session_factory = Mock()
        mock_session_factory.return_value = mock_async_session
        mock_async_scoped_session.session_factory = mock_session_factory

        with patch("transactional_sqlalchemy.config.verify_config"):
            manager = ScopeAndSessionManager(mock_async_scoped_session)

        result = manager.get_new_async_session(force=False)

        assert result == (mock_async_session, mock_async_scoped_session)
        mock_session_factory.assert_called_once_with()


class TestSessionHandler:
    """SessionHandler 클래스 테스트"""

    def setup_method(self):
        """각 테스트 전에 싱글톤 인스턴스 초기화"""
        SessionHandler._SessionHandler__instance = None
        SessionHandler.scoped_session_manager = None

    def test_singleton_pattern(self):
        """싱글톤 패턴이 올바르게 작동하는지 테스트"""
        handler1 = SessionHandler()
        handler2 = SessionHandler()

        assert handler1 is handler2

    def test_get_manager_success(self):
        """매니저가 설정된 경우 get_manager 테스트"""
        mock_manager = Mock(spec=ScopeAndSessionManager)
        SessionHandler.scoped_session_manager = mock_manager

        result = SessionHandler.get_manager()

        assert result is mock_manager

    def test_get_manager_not_initialized(self):
        """매니저가 설정되지 않은 경우 get_manager 테스트"""
        SessionHandler.scoped_session_manager = None

        with pytest.raises(ValueError, match="Session manager not initialized"):
            SessionHandler.get_manager()

    def test_set_manager(self):
        """set_manager 메서드 테스트"""
        mock_manager = Mock(spec=ScopeAndSessionManager)

        SessionHandler.set_manager(mock_manager)

        assert SessionHandler.scoped_session_manager is mock_manager


class TestInitManager:
    """init_manager 함수 테스트"""

    def setup_method(self):
        """각 테스트 전에 싱글톤 인스턴스 초기화"""
        SessionHandler._SessionHandler__instance = None
        SessionHandler.scoped_session_manager = None
        ScopeAndSessionManager._ScopeAndSessionManager__instance = None

    @patch("logging.debug")
    @patch("transactional_sqlalchemy.config.verify_config")
    def test_init_manager_with_scoped_session(self, mock_verify, mock_debug):
        """scoped_session으로 매니저 초기화 테스트"""
        mock_scoped_session = Mock(spec=scoped_session)

        init_manager(mock_scoped_session)

        # SessionHandler가 생성되었는지 확인
        handler = SessionHandler.get_manager()
        assert handler is not None
        assert isinstance(handler, ScopeAndSessionManager)

        # verify_config가 호출되었는지 확인
        mock_verify.assert_called_once_with(scoped_session=mock_scoped_session)

        # 로깅이 호출되었는지 확인
        mock_debug.assert_called()

    @patch("logging.debug")
    @patch("transactional_sqlalchemy.config.verify_config")
    def test_init_manager_with_async_scoped_session(self, mock_verify, mock_debug):
        """async_scoped_session으로 매니저 초기화 테스트"""
        mock_async_scoped_session = Mock(spec=async_scoped_session)

        init_manager(mock_async_scoped_session)

        # SessionHandler가 생성되었는지 확인
        handler = SessionHandler.get_manager()
        assert handler is not None
        assert isinstance(handler, ScopeAndSessionManager)

        # verify_config가 호출되었는지 확인
        mock_verify.assert_called_once_with(scoped_session=mock_async_scoped_session)

        # 로깅이 호출되었는지 확인
        mock_debug.assert_called()

    @patch("transactional_sqlalchemy.config.verify_config")
    def test_init_manager_creates_handler_and_manager(self, mock_verify):
        """init_manager가 핸들러와 매니저를 올바르게 생성하는지 테스트"""
        mock_scoped_session = Mock(spec=scoped_session)

        init_manager(mock_scoped_session)

        # SessionHandler 인스턴스가 생성되었는지 확인
        assert SessionHandler._SessionHandler__instance is not None

        # ScopeAndSessionManager 인스턴스가 생성되었는지 확인
        assert ScopeAndSessionManager._ScopeAndSessionManager__instance is not None

        # 매니저가 핸들러에 설정되었는지 확인
        manager = SessionHandler.get_manager()
        assert manager.scoped_session_ is mock_scoped_session


class TestIntegration:
    """통합 테스트"""

    def setup_method(self):
        """각 테스트 전에 싱글톤 인스턴스 초기화"""
        SessionHandler._SessionHandler__instance = None
        SessionHandler.scoped_session_manager = None
        ScopeAndSessionManager._ScopeAndSessionManager__instance = None

    @patch("transactional_sqlalchemy.config.verify_config")
    def test_full_initialization_flow(self, mock_verify):
        """전체 초기화 플로우 테스트"""
        mock_scoped_session = Mock()
        mock_session = Mock(spec=Session)
        mock_scoped_session.return_value = mock_session

        # session_factory 설정
        mock_session_factory = Mock()
        mock_session_factory.return_value = mock_session
        mock_scoped_session.session_factory = mock_session_factory

        # 초기화
        init_manager(mock_scoped_session)

        # 매니저 사용
        handler = SessionHandler()
        manager = handler.get_manager()

        # 새 세션 생성 (force=True)
        session1, scoped1 = manager.get_new_session(force=True)
        assert session1 is mock_session
        assert scoped1 is mock_scoped_session

        # 새 세션 생성 (force=False) - 커버리지 확보
        session2, scoped2 = manager.get_new_session(force=False)
        assert session2 is mock_session
        assert scoped2 is mock_scoped_session

        # verify_config가 호출되었는지 확인
        mock_verify.assert_called_once_with(scoped_session=mock_scoped_session)
