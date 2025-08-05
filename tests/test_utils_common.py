import logging
from unittest.mock import Mock, patch

from transactional_sqlalchemy.utils.common import get_logger


class TestGetLogger:
    """get_logger 함수 테스트"""

    def setup_method(self):
        """각 테스트 전에 캐시 클리어"""
        get_logger.cache_clear()

    def test_get_logger_creates_logger(self):
        """로거가 정상적으로 생성되는지 테스트"""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "transactional_sqlalchemy"
        assert logger.level == logging.INFO

    def test_get_logger_cached(self):
        """lru_cache로 동일한 로거 인스턴스가 반환되는지 테스트"""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_get_logger_adds_handler_when_no_handlers(self):
        """핸들러가 없을 때 새로운 핸들러가 추가되는지 테스트"""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.hasHandlers.return_value = False
            mock_get_logger.return_value = mock_logger

            # 테스트 실행
            result = get_logger()

            # 검증
            mock_logger.addHandler.assert_called_once()
            mock_logger.setLevel.assert_called_once_with(logging.INFO)
            assert result is mock_logger

    def test_get_logger_skips_handler_when_has_handlers(self):
        """이미 핸들러가 있을 때 새로운 핸들러를 추가하지 않는지 테스트"""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.hasHandlers.return_value = True
            mock_get_logger.return_value = mock_logger

            # 테스트 실행
            result = get_logger()

            # 검증 - addHandler가 호출되지 않아야 함
            mock_logger.addHandler.assert_not_called()
            mock_logger.setLevel.assert_called_once_with(logging.INFO)
            assert result is mock_logger
