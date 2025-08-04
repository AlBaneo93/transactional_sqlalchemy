import logging
from functools import lru_cache


@lru_cache
def get_logger() -> logging.Logger:
    """로거를 생성합니다."""
    logger = logging.getLogger("transactional_sqlalchemy")
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03dZ - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 기본 로깅 레벨 설정
    return logger


def is_async_env() -> bool:
    """비동기 환경인지 확인합니다."""
    try:
        import asyncio

        asyncio.get_running_loop()
        return True
    except (RuntimeError, ImportError):
        return False
