import pytest
from sqlalchemy.ext.asyncio.session import AsyncSession

from tests.conftest import Post
from transactional_sqlalchemy import Propagation, transactional
from transactional_sqlalchemy.repository.base import MODEL_TYPE, BaseCRUDTransactionRepository


class BaseCRUDRequiresTransactionRepositoryImpl(BaseCRUDTransactionRepository[Post]):
    @transactional(propagation=Propagation.REQUIRES)
    async def save(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        return await super().save(model, session=session)

    @transactional(propagation=Propagation.REQUIRES)
    async def save_error(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        await super().save(model)
        raise Exception()


@pytest.fixture(scope="module", autouse=True)
def repository_async() -> BaseCRUDRequiresTransactionRepositoryImpl:
    repo = BaseCRUDRequiresTransactionRepositoryImpl()
    return repo


class TestTransactional:
    @pytest.mark.asyncio
    async def test_save(self, repository_async):
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        await repository_async.save(post)

        assert post.id is not None


class TestRequiresTransactional:
    @pytest.mark.asyncio
    async def test_requires(self, repository_async):
        # 외부의 세션이 없을 때, 정상적으로 세션을 생성하는지 확인
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        try:
            await repository_async.save(post)
        except:
            raise

        assert post.id is not None

    @pytest.mark.asyncio
    async def test_requires_error(self, repository_async):
        # 외부의 세션이 없을 때, 정상적으로 세션을 생성하는지 확인
        post = Post(**{"title": "tests", "content": "tests"})

        with pytest.raises(Exception):
            await repository_async.save_error(post)

        assert post is not None
        assert post.id is None
