from abc import ABC

from src.transactional import Propagation, transactional
from utils import with_transaction_context


class AutoSessionMixIn(ABC):
    """IRepository를 상속받는 모든 클래스의 Async 메서드에 자동으로 `with_transaction_context` 적용
    """

    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()

        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value) and attr_name.startswith('__') is False:
                if not hasattr(attr_value, '_with_transaction_context_decorated'):
                    # 데코레이터를 자동으로 적용
                    with_transaction_context_func = with_transaction_context(attr_value)
                    # 데코레이터가 적용된 함수에 _with_transaction_context_decorated 속성 추가
                    setattr(
                        with_transaction_context_func,
                        '_with_transaction_context_decorated',
                        True,
                    )
                    setattr(cls, attr_name, with_transaction_context_func)


class AutoTransactionalMixIn(ABC ):
    """Repository 클래스에서 상속받으면 자동으로 transactional 데코레이터를 적용하는 추상클래스
    """

    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()

        # 서브클래스에서 정의된 메서드들에 데코레이터를 자동으로 적용
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value) and not attr_name.startswith('__'):
                if not hasattr(attr_value, '_transactional_decorated'):
                    # 데코레이터를 자동으로 적용
                    propagation = getattr(
                        attr_value, '_transactional_propagation', Propagation.REQUIRES
                    )
                    decorated_func = transactional(propagation=propagation)(attr_value)
                    # 데코레이터가 적용된 함수에 _transactional_decorated 속성 추가
                    setattr(decorated_func, '_transactional_decorated', True)
                    setattr(cls, attr_name, decorated_func)


class ITransactionalRepository(AutoTransactionalMixIn, AutoSessionMixIn):
    pass
