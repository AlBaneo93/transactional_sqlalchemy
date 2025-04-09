# 자동으로 trasactional이 적용되는지 테스트
import logging

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session, AsyncSession
from sqlalchemy.orm import scoped_session


from src import transaction_context
from src.interface import ITransactionalRepository
from src.transactional import Propagation, transactional
from tests.async_env.conftest import Post


class TransactionRepositoryImpl(ITransactionalRepository):
    @transactional(propagation=Propagation.REQUIRES)
    async def requires(self, post: Post, session: AsyncSession):
        session.add(post)
        return post

    @transactional(propagation=Propagation.REQUIRES)
    async def requires_error(self, post: Post, session: AsyncSession):
        session.add(post)
        raise Exception("requires error")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new(self, post: Post, session: AsyncSession):
        session.add(post)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new_error(self, post: Post, session: AsyncSession):
        session.add(post)
        raise Exception("tests")

    @transactional(propagation=Propagation.NESTED)
    async def nested(self, post: Post, session: AsyncSession):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        return post

    @transactional(propagation=Propagation.NESTED)
    async def nested_error(self, post: Post, session: AsyncSession):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        raise Exception("tests")  # rollback

    @transactional
    async def default(self, post: Post, session: AsyncSession):
        # 정상적으로 DB 저장이 되는지 확인
        session.add(post)
        await session.commit()
        await session.refresh(post)

        assert post.id is not None


@pytest_asyncio.fixture(scope="session", autouse=True)
def repository() -> TransactionRepositoryImpl:
    repo = TransactionRepositoryImpl()
    return repo


class TestTransactional:
    @pytest.mark.asyncio
    async def test_default(self, repository):
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        try:
            await repository.default(post)
        except:
            raise

        assert post.id is not None


class TestRequiresNewTransactional:
    @pytest.mark.asyncio
    async def test_requires_new(self, repository, transaction):
        async with transaction as sess:
            post = Post(**{"title": "tests", "content": "tests"})
            new_post = Post(**{"title": "new_tests", "content": "new_tests"})
            sess.add(post)

            # 새로운 트랜잭션이 생겨서 따로 실행되어야함
            try:
                await repository.requires_new(new_post)
            except:
                pass

            await sess.commit()
            await sess.refresh(post)

            assert new_post.id is not None
            assert post.id is not None

    async def test_requires_new_error(self, repository, transaction):
        post = Post(**{"title": "tests", "content": "tests"})
        new_post = Post(**{"title": "new_tests", "content": "new_tests"})

        async with transaction as sess:
            sess.add(post)

            # 새로운 트랜잭션이 생겨서 따로 실행되나 롤백
            with pytest.raises(Exception):
                await repository.requires_new_error(new_post)

            await sess.commit()
            await sess.refresh(post)

            assert new_post.id is None
            assert post.id is not None


class TestRequiresTransactional:
    @pytest.mark.asyncio
    async def test_requires(self, repository):
        # 외부의 세션이 없을 때, 정상적으로 세션을 생성하는지 확인
        # 정상적으로 DB에 저장되면 됨
        post = Post(**{"title": "tests", "content": "tests"})

        try:
            await repository.requires(post)
        except:
            raise

        assert post.id is not None

    @pytest.mark.asyncio
    async def test_requires_error(self, repository):
        # 외부의 세션이 없을 때, 정상적으로 세션을 생성하는지 확인
        post = Post(**{"title": "tests", "content": "tests"})

        with pytest.raises(Exception):
            await repository.requires_error(post)

        assert post is not None
        assert post.id is None


class TestNestedTransactional:
    @pytest.mark.asyncio
    async def test_nested(
        self,
        repository,
        transaction,
        scoped_session_: async_scoped_session | scoped_session,
    ):
        # outer와 nested에서 모두 정상적으로 DB 저장이 되는지 확인
        post = Post(**{"title": "tests", "content": "tests"})
        nest_post = Post(**{"title": "nest_test", "content": "nest"})

        async with transaction as sess:
            sess.add(post)

            try:
                await repository.nested(nest_post)
            except Exception:
                raise

            await sess.commit()

        assert post.id is not None

        async with scoped_session_() as sess:
            stmt = select(Post).where(Post.id.in_([nest_post.id, post.id]))
            result = await sess.execute(stmt)
            result = result.scalars().all()
            assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_nested_with_inner_error(self, repository, transaction):
        # netsted 세션은 롤백되나, outer는 정상적으로 commit이 되어야함
        post = Post(**{"title": "tests", "content": "tests"})
        nest_post = Post(**{"title": "nest_test", "content": "nest"})

        # nested 만 롤백 되어야 함
        async with transaction as sess:
            sess.add(post)

            with pytest.raises(Exception):
                await repository.nested_error(nest_post)

            await sess.commit()
            await sess.refresh(post)

        assert post.id is not None
        assert nest_post.id is None

    @pytest.mark.asyncio
    async def test_nested_with_outer_error(
        self,
        repository,
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
                await repository.nested(nest_post)
                raise Exception("outer rollback")

        async with scoped_session_() as sess:
            stmt = select(Post).where(Post.id.in_([nest_post.id, post.id]))
            result = await sess.execute(stmt)
            result = result.scalars().all()
            assert len(result) == 0
