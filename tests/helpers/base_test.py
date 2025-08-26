"""
베이스 테스트 클래스
"""

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from tests.conftest import Post, SampleModel
from tests.factories.post_factory import PostFactory
from tests.factories.sample_model_factory import SampleModelFactory

T = TypeVar("T")


class BaseTest:
    """공통 테스트 기능을 제공하는 베이스 클래스"""

    # 팩토리 인스턴스들
    post_factory = PostFactory
    sample_model_factory = SampleModelFactory

    def create_test_post(self, **kwargs) -> Post:
        """Create a test post using the post factory"""
        return self.post_factory.create_test_post(**kwargs)

    def create_new_post(self, **kwargs) -> Post:
        """Create a new post using the post factory"""
        return self.post_factory.create_new_post(**kwargs)

    def create_sample_model(self, **kwargs) -> SampleModel:
        """Create a sample model using the sample model factory"""
        return self.sample_model_factory.create_test_model(**kwargs)

    def assert_post_saved(self, post: Post) -> None:
        """Assert that a post has been saved successfully"""
        from .assertions import 포스트가_정상적으로_저장되었는지_확인

        포스트가_정상적으로_저장되었는지_확인(post)

    def assert_post_not_saved(self, post: Post) -> None:
        """Assert that a post has not been saved"""
        from .assertions import 포스트가_저장되지_않았는지_확인

        포스트가_저장되지_않았는지_확인(post)

    def assert_model_saved(self, model) -> None:
        """Assert that a model has been saved successfully"""
        from .assertions import 모델이_정상적으로_저장되었는지_확인

        모델이_정상적으로_저장되었는지_확인(model)


class AsyncBaseTest(BaseTest):
    """Base test class for asynchronous tests"""

    async def add_post_to_session_and_flush(self, post: Post, *, session: AsyncSession) -> Post:
        """Add a post to the session and commit the transaction"""
        session.add(post)
        await session.flush()
        await session.refresh(post)
        return post

    async def get_post_from_session(self, post_id: int, *, session: AsyncSession) -> Post:
        """Retrieve a post from the session by ID"""
        from sqlalchemy import select

        from tests.conftest import Post

        stmt = select(Post).where(Post.id == post_id)
        result = await session.execute(stmt)
        return result.scalars().first()


class SyncBaseTest(BaseTest):
    """Base test class for synchronous tests"""

    def add_post_to_session_and_flush(self, post: Post, *, session: Session = None) -> Post:
        """Add a post to the session and commit the transaction"""
        session.add(post)
        session.flush()
        session.refresh(post)
        return post

    def get_post_from_session(self, post_id: int, *, session: Session = None) -> Post:
        """Retrieve a post from the session by ID"""
        from sqlalchemy import select

        from tests.conftest import Post

        stmt = select(Post).where(Post.id == post_id)
        result = session.execute(stmt)
        return result.scalars().first()
