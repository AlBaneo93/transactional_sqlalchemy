from abc import ABC

from transactional_sqlalchemy.decorator.transactional import transactional
from transactional_sqlalchemy.enums import Propagation
from transactional_sqlalchemy.utils.utils import with_transaction_context


class AutoSessionMixIn(ABC):
    """IRepository를 상속받는 모든 클래스의 Async 메서드에 자동으로 `with_transaction_context` 적용"""

    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()

        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value) and attr_name.startswith("__") is False:
                if not hasattr(attr_value, "_with_transaction_context_decorated"):
                    # 데코레이터를 자동으로 적용
                    with_transaction_context_func = with_transaction_context(attr_value)
                    # 데코레이터가 적용된 함수에 _with_transaction_context_decorated 속성 추가
                    setattr(
                        with_transaction_context_func,
                        "_with_transaction_context_decorated",
                        True,
                    )
                    setattr(cls, attr_name, with_transaction_context_func)


class AutoTransactionalMixIn(ABC):
    """Repository 클래스에서 상속받으면 자동으로 transactional 데코레이터를 적용하는 추상클래스"""

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # 현재 클래스에서 접근 가능한 모든 메서드 가져오기
        for attr_name in dir(cls):
            # private 메서드와 magic 메서드 제외
            if attr_name.startswith("_"):
                continue

            attr_value = getattr(cls, attr_name)

            # callable이고 메서드인지 확인
            if not callable(attr_value):
                continue

            # 이미 transactional 데코레이터가 적용되었는지 확인
            if hasattr(attr_value, "_transactional_decorated"):
                print(f"✅ {cls.__name__}.{attr_name} - 이미 데코레이터 적용됨, 건너뜀")
                continue

            # 제외할 메서드들 (필요에 따라 수정)
            exclude_methods = {
                "model",  # 속성
            }

            if attr_name in exclude_methods:
                continue

            # Repository 관련 메서드인지 확인 (선택적)
            # repository_methods = {
            #         'save', 'find_by_id', 'find_all', 'find_all_by_id',
            #         'exists_by_id', 'count', 'delete', 'update', 'create'
            # }

            # 모든 메서드에 적용하거나, 특정 메서드만 적용할지 선택
            # 옵션 1: 모든 메서드에 적용
            should_decorate = True

            # 옵션 2: 특정 메서드만 적용 (주석 해제하여 사용)
            # should_decorate = attr_name in repository_methods

            if should_decorate:
                try:
                    # 데코레이터 적용
                    propagation = getattr(attr_value, "_transactional_propagation", Propagation.REQUIRES)
                    decorated_func = transactional(propagation=propagation)(attr_value)
                    setattr(decorated_func, "_transactional_decorated", True)
                    setattr(cls, attr_name, decorated_func)

                except Exception:
                    pass


class ISessionRepository(AutoSessionMixIn):
    """세션을 사용하는 Repository에 대한 인터페이스"""

    pass


class ITransactionalRepository(AutoTransactionalMixIn, AutoSessionMixIn):
    pass
