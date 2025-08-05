import logging
from functools import lru_cache


@lru_cache
def get_logger() -> logging.Logger:
    """로거를 생성합니다.

    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
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
