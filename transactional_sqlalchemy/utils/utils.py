import functools
import inspect
from inspect import iscoroutinefunction, unwrap
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from transactional_sqlalchemy.config import SessionHandler, transaction_context
from transactional_sqlalchemy.utils.structure import Stack


def allocate_session_in_args(bound_args: inspect.BoundArguments):
    if "session" in bound_args.arguments:
        sess = bound_args.arguments["session"]
        if sess is None or (sess is not None and isinstance(sess, (Session, AsyncSession))):
            # 스택에서 현재 세션 가져오기
            stack: Stack[AsyncSession | Session] = transaction_context.get()

            if stack.size() > 0:
                # 스택에 세션이 있으면 현재 세션 사용
                current_session = stack.peek()
                bound_args.arguments["session"] = current_session
            else:
                # 스택이 비어있으면 새로운 세션 생성
                new_session, _ = SessionHandler().get_manager().get_new_session()
                stack.push(new_session)
                bound_args.arguments["session"] = new_session


def with_transaction_context(func):
    """함수의 session 파라미터를 자동으로 transaction_context에서 가져오도록 설정하는 데코레이터"""
    sig = inspect.signature(func)

    if iscoroutinefunction(unwrap(func)):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            bound_args = sig.bind_partial(*args, **kwargs)
            bound_args.apply_defaults()
            allocate_session_in_args(bound_args)

            return await func(*bound_args.args, **bound_args.kwargs)

        return async_wrapper
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound_args = sig.bind_partial(*args, **kwargs)
            bound_args.apply_defaults()
            allocate_session_in_args(bound_args)

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper


def is_orm_instance(obj):
    return hasattr(obj, "__mapper__") and hasattr(obj.__class__, "__table__")


def find_orm_instance(*args, **kwargs) -> list:
    models = []

    def _extract_models(obj):
        # ORM 모델 인스턴스 검사
        if is_orm_instance(obj):
            models.append(obj)
        # 리스트, 튜플, 셋 등 iterable 이면서 문자열 제외
        elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
            for item in obj:
                _extract_models(item)

    for obj in list(args) + list(kwargs.values()):
        _extract_models(obj)

    return models


def reset_pk_fields(models: Any):
    """ORM 모델 인스턴스의 기본 키 필드를 초기화합니다.
    주로 트랜잭션 롤백 후에 사용됩니다.

    Args:
        models (list): ORM 모델 인스턴스 리스트

    """
    # 리스트인지 확인
    if isinstance(models, (list, tuple, set)):
        for model in models:
            reset_pk_fields(model)
        return

    # 단일 ORM 인스턴스라 가정
    pk_columns = models.__mapper__.primary_key
    for col in pk_columns:
        setattr(models, col.key, None)


def add_session_to_context(sess_: AsyncSession | Session) -> None:
    """트랜잭션 컨텍스트에 세션을 추가합니다."""
    if sess_ is None:
        raise ValueError("세션이 None입니다.")
    stack: Stack[AsyncSession | Session] = transaction_context.get()
    stack.push(sess_)


def get_session_from_context() -> AsyncSession | Session | None:
    """트랜잭션 컨텍스트에서 세션을 가져옵니다."""
    stack: Stack[AsyncSession | Session] = transaction_context.get()
    if stack.size() <= 0:
        return None
    return stack.peek()  # 현재 세션을 반환


def remove_session_from_context() -> None:
    """트랜잭션 컨텍스트에서 세션을 제거합니다."""
    stack: Stack[AsyncSession | Session] = transaction_context.get()
    if stack.size() <= 0:
        raise ValueError("트랜잭션 컨텍스트에 세션이 없습니다.")
    stack.pop()  # 현재 세션을 제거
    if stack.size() == 0:
        transaction_context.set(Stack())  # 스택이 비어있으면 초기화


def get_session_stack_size() -> int:
    """트랜잭션 컨텍스트의 세션 스택 크기를 반환합니다."""
    stack: Stack[AsyncSession | Session] = transaction_context.get()
    return stack.size() if stack else 0


def has_active_transaction() -> bool:
    """현재 활성 트랜잭션이 있는지 확인합니다."""
    return get_session_stack_size() > 0


def get_current_transaction_depth() -> int:
    """현재 트랜잭션 중첩 깊이를 반환합니다."""
    return get_session_stack_size()
