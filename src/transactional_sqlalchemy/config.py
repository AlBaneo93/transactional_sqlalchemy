import logging
from contextvars import ContextVar
from typing import Optional, Union

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
)
from sqlalchemy.orm import Session, scoped_session


def verify_config(**kwargs):
    """

    Args:
        **kwargs ():

    Returns:

    """
    if "scoped_session" not in kwargs:
        raise ValueError("scoped_session is required")


transaction_context: ContextVar[Optional[Session|AsyncSession]] = ContextVar(
    "transaction_context", default=None
)


class ScopeAndSessionManager:
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, scoped_session_: Union[async_scoped_session, scoped_session]):
        """

        Args:
            scoped_session_ ():
        """
        verify_config(**{"scoped_session": scoped_session_})
        self.scoped_session_: async_scoped_session | scoped_session = scoped_session_
        logging.debug(f"Session manager initialized {self.scoped_session_ is not None}")

    def get_new_session(self, force: bool = False) -> Union[Session, AsyncSession]:
        if force:
            return self.scoped_session_()
        else:
            return self.scoped_session_.session_factory()


class SessionHandler:
    scoped_session_manager: ScopeAndSessionManager = None
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def get_manager(cls) -> ScopeAndSessionManager:
        if cls.scoped_session_manager is None:
            raise ValueError("Session manager not initialized.")
        return cls.scoped_session_manager

    @classmethod
    def set_manager(cls, manager: ScopeAndSessionManager) -> None:
        cls.scoped_session_manager = manager


def init_manager(
    session: Union[async_scoped_session, scoped_session],
) -> None:
    handler = SessionHandler()
    manager = ScopeAndSessionManager(scoped_session_=session)
    handler.set_manager(manager)
    logging.debug(f"Session manager initialized")
