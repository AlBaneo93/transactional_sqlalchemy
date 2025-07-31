from __future__ import annotations

import logging

import pytest
from sqlalchemy.ext.asyncio.scoping import async_scoped_session
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.scoping import scoped_session

from tests.conftest import Post
from transactional_sqlalchemy import Propagation, transaction_context, transactional
from transactional_sqlalchemy.repository.base import MODEL_TYPE, BaseCRUDTransactionRepository


class BaseNestedCRUDTransactionRepositoryImpl(BaseCRUDTransactionRepository[Post]):
    @transactional(propagation=Propagation.NESTED)
    async def save(self, model: MODEL_TYPE, *, session: AsyncSession) -> MODEL_TYPE:
        return await super().save(model, session=session)

    @transactional(propagation=Propagation.NESTED)
    async def save_error(self, model: MODEL_TYPE, *, session: AsyncSession = None) -> MODEL_TYPE:
        await super().save(model)
        raise Exception()


@pytest.fixture(scope="module", autouse=True)
def repository_async() -> BaseNestedCRUDTransactionRepositoryImpl:
    repo = BaseNestedCRUDTransactionRepositoryImpl(Post)
    return repo


class TestTransactional:
    @pytest.mark.asyncio
    async def test_save(self, repository_async):
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        await repository_async.save(post)

        assert post.id is not None


class TestNestedTransactional:
    @pytest.mark.asyncio
    async def test_nested(
        self,
        repository_async,
        transaction_async,
        scoped_session_: async_scoped_session | scoped_session,
    ):
        # outer와 nested에서 모두 정상적으로 DB 저장이 되는지 확인
        post = Post(**{"title": "tests", "content": "tests"})
        nest_post = Post(**{"title": "nest_test", "content": "nest"})

        async with transaction_async as sess:
            sess.add(post)

            await repository_async.save(nest_post)

            await sess.commit()

        assert post.id is not None

        async with scoped_session_() as sess:
            stmt = select(Post).where(Post.id.in_([nest_post.id, post.id]))
            result = await sess.execute(stmt)
            result = result.scalars().all()
            assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_nested_with_inner_error(self, repository_async, transaction_async):
        # netsted 세션은 롤백되나, outer는 정상적으로 commit이 되어야함
        post = Post(**{"title": "tests", "content": "tests"})
        nest_post = Post(**{"title": "nest_test", "content": "nest"})

        # nested 만 롤백 되어야 함
        async with transaction_async as sess:
            sess.add(post)

            with pytest.raises(Exception):
                await repository_async.save_error(nest_post)

            await sess.commit()
            await sess.refresh(post)

        assert post.id is not None
        assert nest_post.id is None

    @pytest.mark.asyncio
    async def test_nested_with_outer_error(
        self,
        repository_async,
        scoped_session_: async_scoped_session | scoped_session,
    ):
        try:
            # init
            sess = scoped_session_()
            transaction_context.set(sess)

        except:
            logging.exception("")
            raise

        post = Post(**{"title": "tests", "content": "tests"})
        nest_post = Post(**{"title": "nest_tests", "content": "nest_tests"})

        sess = transaction_context.get()
        assert sess is not None

        with pytest.raises(Exception):
            # outer, nested 모두 롤백 되어야 함
            async with sess() as tx:
                tx.add(post)
                await repository_async.nested(nest_post)
                raise Exception("outer rollback")

        async with scoped_session_() as sess:
            stmt = select(Post).where(Post.id.in_([nest_post.id, post.id]))
            result = await sess.execute(stmt)
            result = result.scalars().all()
            assert len(result) == 0
