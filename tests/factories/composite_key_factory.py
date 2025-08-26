"""
복합키 모델 테스트 데이터 팩토리
"""

from tests.conftest import OrderItem, UserRolePermission


class OrderItemFactory:
    """Factory class for creating OrderItem test data"""

    @classmethod
    def create_basic_order_item(
        cls, order_id: int = 1, product_id: int = 100, quantity: int = 1, price: int = 1000, **kwargs
    ) -> OrderItem:
        """Create a basic OrderItem with default values"""
        data = {"order_id": order_id, "product_id": product_id, "quantity": quantity, "price": price}
        data.update(kwargs)
        return OrderItem(**data)

    @classmethod
    def create_test_order_item(cls, **kwargs) -> OrderItem:
        """Create an OrderItem for general testing purposes"""
        return cls.create_basic_order_item(order_id=1, product_id=100, quantity=2, price=1000, **kwargs)

    @classmethod
    def create_new_order_item(cls, **kwargs) -> OrderItem:
        """Create a new OrderItem with different default values"""
        return cls.create_basic_order_item(order_id=3, product_id=200, quantity=5, price=1500, **kwargs)


class UserRolePermissionFactory:
    """Factory class for creating UserRolePermission test data"""

    @classmethod
    def create_basic_permission(
        cls, user_id: int = 1, role_id: int = 1, permission_id: int = 1, **kwargs
    ) -> UserRolePermission:
        """Create a basic UserRolePermission with default values"""
        data = {"user_id": user_id, "role_id": role_id, "permission_id": permission_id}
        data.update(kwargs)
        return UserRolePermission(**data)

    @classmethod
    def create_test_permission(cls, **kwargs) -> UserRolePermission:
        """Create a UserRolePermission for general testing purposes"""
        return cls.create_basic_permission(user_id=1, role_id=1, permission_id=2, **kwargs)

    @classmethod
    def create_multiple_permissions(cls) -> list[UserRolePermission]:
        """Create multiple UserRolePermissions for comprehensive testing"""
        return [
            cls.create_basic_permission(user_id=1, role_id=1, permission_id=1),
            cls.create_basic_permission(user_id=1, role_id=1, permission_id=2),
            cls.create_basic_permission(user_id=1, role_id=2, permission_id=1),
            cls.create_basic_permission(user_id=2, role_id=1, permission_id=1),
        ]
