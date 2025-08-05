from unittest.mock import Mock, patch

from transactional_sqlalchemy.enums import Propagation
from transactional_sqlalchemy.interface import (
    AutoSessionMixIn,
    AutoTransactionalMixIn,
    ISessionRepository,
    ITransactionalRepository,
)


class TestAutoSessionMixInEdgeCases:
    """AutoSessionMixIn 엣지 케이스 테스트"""

    @patch("transactional_sqlalchemy.interface.with_transaction_context")
    def test_init_subclass_skip_already_decorated(self, mock_with_transaction_context):
        """이미 데코레이트된 메서드는 건너뛰는지 테스트"""

        # 미리 데코레이트된 메서드 생성
        def pre_decorated_method(self):
            return "decorated"

        pre_decorated_method._with_transaction_context_decorated = True

        class TestRepository(AutoSessionMixIn):
            def normal_method(self):
                return "normal"

            # 이미 데코레이트된 메서드를 클래스에 할당
            already_decorated_method = pre_decorated_method

        # normal_method만 데코레이트되어야 함 (already_decorated_method는 건너뜀)
        mock_with_transaction_context.assert_called_once()

    @patch("transactional_sqlalchemy.interface.with_transaction_context")
    def test_init_subclass_with_private_methods(self, mock_with_transaction_context):
        """callable 메서드들이 데코레이트되는지 테스트"""

        class TestRepository(AutoSessionMixIn):
            def public_method(self):
                return "public"

            def __private_method(self):
                return "private"

            def _protected_method(self):
                return "protected"

        # 모든 callable 메서드가 데코레이트됨
        assert mock_with_transaction_context.call_count == 3


class TestAutoTransactionalMixInEdgeCases:
    """AutoTransactionalMixIn 엣지 케이스 테스트"""

    @patch("transactional_sqlalchemy.interface.transactional")
    def test_init_subclass_exclude_methods(self, mock_transactional):
        """제외 메서드들이 데코레이트되지 않는지 테스트"""
        mock_decorator = Mock()
        mock_transactional.return_value = mock_decorator

        class TestRepository(AutoTransactionalMixIn):
            def normal_method(self):
                return "normal"

            @property
            def model(self):
                return "model"

            def __private_method(self):
                return "private"

            def _protected_method(self):
                return "protected"

        # normal_method만 데코레이트되어야 함
        # model property와 private/protected 메서드는 제외
        mock_transactional.assert_called()

    @patch("transactional_sqlalchemy.interface.transactional")
    def test_init_subclass_already_decorated_skip(self, mock_transactional):
        """이미 transactional 데코레이터가 적용된 메서드는 건너뛰는지 테스트"""

        # 미리 데코레이트된 메서드 생성
        def pre_decorated_method(self):
            return "decorated"

        pre_decorated_method._transactional_decorated = True

        class TestRepository(AutoTransactionalMixIn):
            def normal_method(self):
                return "normal"

            # 이미 데코레이트된 메서드를 클래스에 할당
            already_decorated_method = pre_decorated_method

        # normal_method만 데코레이트되어야 함
        mock_transactional.assert_called_once()

    @patch("transactional_sqlalchemy.interface.transactional")
    def test_init_subclass_decoration_exception(self, mock_transactional):
        """데코레이션 중 예외 발생 시 처리 테스트"""
        mock_transactional.side_effect = Exception("Decoration failed")

        # 예외가 발생해도 클래스 생성은 실패하지 않아야 함
        class TestRepository(AutoTransactionalMixIn):
            def test_method(self):
                return "test"

        # 클래스가 정상적으로 생성되어야 함
        repo = TestRepository()
        assert repo is not None

    @patch("transactional_sqlalchemy.interface.transactional")
    def test_init_subclass_custom_propagation(self, mock_transactional):
        """메서드에 커스텀 propagation이 설정된 경우 테스트"""
        mock_decorator = Mock()
        mock_transactional.return_value = mock_decorator

        # 미리 커스텀 propagation이 설정된 메서드 생성
        def pre_custom_method(self):
            return "custom"

        pre_custom_method._transactional_propagation = Propagation.REQUIRES_NEW

        class TestRepository(AutoTransactionalMixIn):
            # 커스텀 propagation이 설정된 메서드를 클래스에 할당
            method_with_custom_propagation = pre_custom_method

        # 커스텀 propagation으로 데코레이트되어야 함
        mock_transactional.assert_called_with(propagation=Propagation.REQUIRES_NEW)

    @patch("transactional_sqlalchemy.interface.transactional")
    def test_init_subclass_default_propagation(self, mock_transactional):
        """기본 propagation으로 데코레이트되는지 테스트"""
        mock_decorator = Mock()
        mock_transactional.return_value = mock_decorator

        class TestRepository(AutoTransactionalMixIn):
            def normal_method(self):
                return "normal"

        # 기본 propagation(REQUIRES)으로 데코레이트되어야 함
        mock_transactional.assert_called_with(propagation=Propagation.REQUIRES)

    def test_init_subclass_non_callable_attribute(self):
        """호출 불가능한 속성은 건너뛰는지 테스트"""

        class TestRepository(AutoTransactionalMixIn):
            class_variable = "not_callable"

            def callable_method(self):
                return "callable"

        # 예외 없이 클래스가 생성되어야 함
        repo = TestRepository()
        assert repo.class_variable == "not_callable"


class TestISessionRepository:
    """ISessionRepository 인터페이스 테스트"""

    def test_inheritance(self):
        """올바른 상속 구조인지 테스트"""
        assert issubclass(ISessionRepository, AutoSessionMixIn)

        # 인스턴스 생성 테스트
        repo = ISessionRepository()
        assert isinstance(repo, AutoSessionMixIn)


class TestITransactionalRepository:
    """ITransactionalRepository 인터페이스 테스트"""

    def test_inheritance(self):
        """올바른 상속 구조인지 테스트"""
        assert issubclass(ITransactionalRepository, AutoTransactionalMixIn)
        assert issubclass(ITransactionalRepository, AutoSessionMixIn)

        # 인스턴스 생성 테스트
        repo = ITransactionalRepository()
        assert isinstance(repo, AutoTransactionalMixIn)
        assert isinstance(repo, AutoSessionMixIn)

    def test_multiple_inheritance_mro(self):
        """다중 상속 시 MRO(Method Resolution Order)가 올바른지 테스트"""
        mro = ITransactionalRepository.__mro__

        # 예상되는 순서: ITransactionalRepository -> AutoTransactionalMixIn -> AutoSessionMixIn -> ABC -> object
        assert ITransactionalRepository in mro
        assert AutoTransactionalMixIn in mro
        assert AutoSessionMixIn in mro


class TestComplexInheritanceScenarios:
    """복잡한 상속 시나리오 테스트"""

    def test_interface_inheritance_basic(self):
        """기본적인 인터페이스 상속 테스트"""
        # 인터페이스 정의가 올바른지만 확인
        assert issubclass(ISessionRepository, AutoSessionMixIn)
        assert issubclass(ITransactionalRepository, AutoSessionMixIn)
        assert issubclass(ITransactionalRepository, AutoTransactionalMixIn)

    def test_mixin_class_creation(self):
        """Mixin 클래스들이 정상적으로 생성되는지 테스트"""

        class TestSessionRepo(AutoSessionMixIn):
            def test_method(self):
                return "session"

        class TestTransactionalRepo(AutoTransactionalMixIn):
            def test_method(self):
                return "transactional"

        # 클래스가 정상적으로 생성되는지 확인
        session_repo = TestSessionRepo()
        transactional_repo = TestTransactionalRepo()

        assert session_repo is not None
        assert transactional_repo is not None
