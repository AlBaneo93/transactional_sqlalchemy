"""
Post 모델 테스트 데이터 팩토리
"""

from tests.conftest import Post


class PostFactory:
    """Factory class for creating Post model test data"""

    _default_data = {"title": "Default Title", "content": "Default Content"}

    @classmethod
    def create_default_post(cls, **kwargs) -> Post:
        """Create a basic default post with minimal data"""
        data = cls._default_data.copy()
        data.update(kwargs)
        return Post(**data)

    @classmethod
    def create_test_post(cls, **kwargs) -> Post:
        """Create a post for general testing purposes"""
        data = {"title": "Test Title", "content": "Test Content"}
        data.update(kwargs)
        return Post(**data)

    @classmethod
    def create_new_post(cls, suffix: str = "new", **kwargs) -> Post:
        """Create a new post with customizable suffix for differentiation"""
        data = {"title": f"New Title {suffix}", "content": f"New Content {suffix}"}
        data.update(kwargs)
        return Post(**data)

    @classmethod
    def create_nested_test_post(cls, **kwargs) -> Post:
        """Create a post specifically for nested transaction testing"""
        data = {"title": "Nested Test Title", "content": "Nested Test Content"}
        data.update(kwargs)
        return Post(**data)

    @classmethod
    def create_outer_transaction_post(cls, **kwargs) -> Post:
        """Create a post for outer transaction testing scenarios"""
        data = {"title": "Outer Transaction Post", "content": "Outer Transaction Content"}
        data.update(kwargs)
        return Post(**data)

    @classmethod
    def create_inner_transaction_post(cls, **kwargs) -> Post:
        """Create a post for inner transaction testing scenarios"""
        data = {"title": "Inner Transaction Post", "content": "Inner Transaction Content"}
        data.update(kwargs)
        return Post(**data)
