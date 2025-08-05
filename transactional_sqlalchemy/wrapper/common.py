from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import Session

from transactional_sqlalchemy.config import ScopeAndSessionManager


def __check_is_commit(
    exc: Exception, rollback_for: tuple[type[Exception]], no_rollback_for: tuple[type[Exception], ...]
):
    if any(isinstance(exc, exc_type) for exc_type in no_rollback_for):
        # 롤백 대상이 아닌 경우 commit
        return True

    elif any(isinstance(exc, exc_type) for exc_type in rollback_for):
        # 롤백 대상 예외인 경우 롤백
        return False

    return False


def __get_safe_kwargs(kwargs):
    rollback_for: tuple[type[Exception]] = kwargs.get("__rollback_for__", (Exception,))
    no_rollback_for: tuple[type[Exception], ...] = kwargs.get("__no_rollback_for__", ())
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}

    return kwargs, no_rollback_for, rollback_for


def get_new_session(
    manager: ScopeAndSessionManager, force: bool = False
) -> tuple[Session, scoped_session] | tuple[AsyncSession, async_scoped_session]:
    return manager.get_new_async_session(force=force)


def set_read_only(sess: Session | AsyncSession) -> Generator[None, Any, None]:
    try:
        sess.autoflush = False
        yield
    finally:
        sess.autoflush = True


def get_current_session_objects(session) -> set:
    return set(list(session.new) + list(session.identity_map.values()))


def reset_savepoint_objects(session: Session | AsyncSession, before_objects: set):
    current_objects = set(session.identity_map.values())
    new_objects = current_objects - before_objects

    # 세션에서 현재 추적 중인 모든 객체를 가져옴
    for obj in new_objects:
        state = inspect(obj)

        if not state.persistent and not state.pending:
            continue  # 이미 detached거나 transient인 객체는 건너뜀

        if state.detached:
            continue

        # 1. PK 초기화
        for pk_col in state.mapper.primary_key:
            setattr(obj, pk_col.key, None)

        # 2. 세션에서 제거
        session.expunge(obj)
