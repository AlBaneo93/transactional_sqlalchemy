import pytest
from sqlalchemy.ext.asyncio.session import AsyncSession

from tests.conftest import Post
from transactional_sqlalchemy import Propagation, transactional
from transactional_sqlalchemy.repository.base import MODEL_TYPE, BaseCRUDTransactionRepository


class BaseRequiresNewCRUDTransactionRepositoryImpl(BaseCRUDTransactionRepository[Post]):
    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def save(self, model: MODEL_TYPE, *, session: AsyncSession = None) -> MODEL_TYPE:
        return await super().save(model)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def save_error(self, model: MODEL_TYPE, *, session: AsyncSession = None) -> MODEL_TYPE:
        await super().save(model)
        raise Exception()


@pytest.fixture(scope="module", autouse=True)
def repository_async() -> BaseRequiresNewCRUDTransactionRepositoryImpl:
    repo = BaseRequiresNewCRUDTransactionRepositoryImpl(Post)
    return repo


class TestTransactional:
    @pytest.mark.asyncio
    async def test_save(self, repository_async):
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        await repository_async.save(post)

        assert post.id is not None


class TestRequiresNewTransactional:
    @pytest.mark.asyncio
    async def test_requires_new(self, repository_async, transaction_async):
        async with transaction_async as sess:
            post = Post(**{"title": "tests", "content": "tests"})
            new_post = Post(**{"title": "new_tests", "content": "new_tests"})
            sess.add(post)

            # 새로운 트랜잭션이 생겨서 따로 실행되어야함
            await repository_async.save(new_post)

            await sess.commit()
            await sess.refresh(post)

            assert new_post.id is not None
            assert post.id is not None

    async def test_requires_new_error(self, repository_async, transaction_async):
        post = Post(**{"title": "tests", "content": "tests"})
        new_post = Post(**{"title": "new_tests", "content": "new_tests"})

        async with transaction_async as sess:
            sess.add(post)

            # 새로운 트랜잭션이 생겨서 따로 실행되나 롤백
            with pytest.raises(Exception):
                await repository_async.save_error(new_post)

            await sess.commit()
            await sess.refresh(post)

            assert new_post.id is None
            assert post.id is not None
