"""
비동기 환경 트랜잭션 리포지토리 테스트
"""

from __future__ import annotations

import logging

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from sqlalchemy.orm import scoped_session

from tests.conftest import Post
from tests.helpers.assertions import (
    async_두_포스트가_모두_존재하는지_확인,
    포스트가_저장되지_않았는지_확인,
    포스트가_정상적으로_저장되었는지_확인,
)
from transactional_sqlalchemy import (
    ISessionRepository,
    ITransactionalRepository,
    Propagation,
    transaction_context,
    transactional,
)
from transactional_sqlalchemy.utils.structure import Stack

from ..helpers.base_test import AsyncBaseTest


class TransactionAsyncRepositoryImpl(ITransactionalRepository):
    @transactional(propagation=Propagation.REQUIRES)
    async def requires(self, post: Post, *, session: AsyncSession):
        session.add(post)
        await session.flush()
        return post

    @transactional(propagation=Propagation.REQUIRES)
    async def requires_error(self, post: Post, *, session: AsyncSession):
        session.add(post)
        raise Exception("requires error")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new(self, post: Post, *, session: AsyncSession):
        session.add(post)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new_error(self, post: Post, *, session: AsyncSession):
        session.add(post)
        raise Exception("tests")

    @transactional(propagation=Propagation.NESTED)
    async def nested(self, post: Post, *, session: AsyncSession):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        return post

    @transactional(propagation=Propagation.NESTED)
    async def nested_error(self, post: Post, *, session: AsyncSession):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        raise Exception("tests")  # rollback

    @transactional
    async def default(self, post: Post, *, session: AsyncSession):
        # 정상적으로 DB 저장이 되는지 확인
        session.add(post)
        await session.commit()
        await session.refresh(post)

        assert post.id is not None


@pytest_asyncio.fixture(scope="module", autouse=True)
def repository_async() -> TransactionAsyncRepositoryImpl:
    repo = TransactionAsyncRepositoryImpl()
    return repo


class TestTransactional(AsyncBaseTest):
    """기본 트랜잭션 테스트"""

    @pytest.mark.asyncio
    async def test_기본_트랜잭션이_정상적으로_작동하는지_확인(self, repository_async):
        """기본 트랜잭션 데코레이터가 정상적으로 작동하는지 확인"""
        # Given
        post = self.create_test_post()

        # When
        await repository_async.default(post)

        # Then
        self.assert_post_saved(post)


class TestRequiresNewTransactional(AsyncBaseTest):
    """REQUIRES_NEW 트랜잭션 전파 테스트"""

    @pytest.mark.asyncio
    async def test_requires_new_전파가_새로운_트랜잭션으로_실행되는지_확인(self, repository_async, transaction_async):
        """REQUIRES_NEW 전파가 새로운 트랜잭션에서 실행되는지 확인"""
        # Given
        async with transaction_async as sess:
            post = self.create_test_post()
            new_post = self.create_new_post()

            # 외부 트랜잭션에 포스트 추가
            await self.add_post_to_session_and_flush(post, session=sess)

            # When - 새로운 트랜잭션에서 실행
            await repository_async.requires_new(new_post)

            # Then - 두 포스트 모두 저장되어야 함
            포스트가_정상적으로_저장되었는지_확인(new_post)
            포스트가_정상적으로_저장되었는지_확인(post)

    @pytest.mark.asyncio
    async def test_requires_new_전파에서_오류_발생시_외부_트랜잭션은_정상_커밋되는지_확인(
        self, repository_async, transaction_async
    ):
        """REQUIRES_NEW 전파에서 오류 발생시 외부 트랜잭션은 정상 커밋되는지 확인"""
        # Given
        post = self.create_test_post()
        new_post = self.create_new_post()

        async with transaction_async as sess:
            await self.add_post_to_session_and_flush(post, session=sess)

            # When & Then - 새로운 트랜잭션에서 오류 발생
            with pytest.raises(Exception):
                await repository_async.requires_new_error(new_post)

            # 외부 트랜잭션은 정상 커밋되어야 함
            await sess.commit()
            await sess.refresh(post)

            # 새로운 포스트는 저장되지 않았지만 외부 포스트는 저장되어야 함
            포스트가_저장되지_않았는지_확인(new_post)
            포스트가_정상적으로_저장되었는지_확인(post)


class TestRequiresTransactional(AsyncBaseTest):
    """REQUIRES 트랜잭션 전파 테스트"""

    @pytest.mark.asyncio
    async def test_requires_전파가_정상적으로_세션을_생성하고_저장하는지_확인(self, repository_async):
        """REQUIRES 전파가 정상적으로 세션을 생성하고 저장하는지 확인"""
        # Given - 외부 세션이 없는 상황
        post = self.create_test_post()

        # When
        await repository_async.requires(post)

        # Then
        self.assert_post_saved(post)

    @pytest.mark.asyncio
    async def test_requires_전파에서_오류_발생시_롤백되는지_확인(self, repository_async):
        """REQUIRES 전파에서 오류 발생시 롤백되는지 확인"""
        # Given
        post = self.create_test_post()

        # When & Then
        with pytest.raises(Exception):
            await repository_async.requires_error(post)

        # 포스트가 저장되지 않았는지 확인
        포스트가_저장되지_않았는지_확인(post)


class TestNestedTransactional(AsyncBaseTest):
    """NESTED 트랜잭션 전파 테스트"""

    @pytest.mark.asyncio
    async def test_nested_전파가_외부와_내부_모두_정상_저장되는지_확인(
        self,
        repository_async,
        transaction_async,
        scoped_session_: async_scoped_session | scoped_session,
    ):
        """NESTED 전파가 외부와 내부 모두 정상 저장되는지 확인"""
        # Given
        post = self.create_test_post()
        nest_post = self.post_factory.create_nested_test_post()

        async with transaction_async as sess:
            # 외부 트랜잭션에 포스트 추가
            await self.add_post_to_session_and_flush(post, session=sess)

            # When - 중첩 트랜잭션 실행
            await repository_async.nested(nest_post)

            # 외부 트랜잭션 커밋
            await sess.commit()

        # Then - 두 포스트 모두 저장되어야 함
        self.assert_post_saved(post)

        # 새로운 세션에서 두 포스트 모두 조회되는지 확인
        async with scoped_session_() as sess:
            await async_두_포스트가_모두_존재하는지_확인(sess, post, nest_post)

    @pytest.mark.asyncio
    async def test_nested_전파에서_내부_오류시_외부는_정상_커밋되는지_확인(self, repository_async, transaction_async):
        """NESTED 전파에서 내부 오류시 외부는 정상 커밋되는지 확인"""
        # Given
        post = self.create_test_post()
        nest_post = self.post_factory.create_nested_test_post()

        async with transaction_async as sess:
            # 외부 트랜잭션에 포스트 추가
            await self.add_post_to_session_and_flush(post, session=sess)

            # When & Then - 중첩 트랜잭션에서 오류 발생
            with pytest.raises(Exception):
                await repository_async.nested_error(nest_post)

            # 외부 트랜잭션은 정상 커밋되어야 함
            await sess.commit()
            await sess.refresh(post)

        # Then - 외부 포스트만 저장되고 중첩 포스트는 저장되지 않아야 함
        self.assert_post_saved(post)
        포스트가_저장되지_않았는지_확인(nest_post)

    @pytest.mark.asyncio
    async def test_nested_전파에서_외부_오류시_모두_롤백되는지_확인(
        self,
        repository_async,
        scoped_session_: async_scoped_session | scoped_session,
    ):
        """NESTED 전파에서 외부 오류시 모두 롤백되는지 확인"""
        # Given - 세션 초기화
        stack = Stack()
        try:
            sess = scoped_session_()
            stack.push(sess)
            transaction_context.set(stack)
        except Exception:
            logging.exception("세션 초기화 실패")
            raise

        post: Post = self.create_test_post()
        nest_post: Post = self.post_factory.create_nested_test_post()

        sess_ = transaction_context.get()
        assert sess_ is not None

        # When & Then - 외부 트랜잭션에서 오류 발생
        with pytest.raises(Exception, match="outer rollback"):
            async with sess_.peek() as tx:
                await self.add_post_to_session_and_flush(post, session=tx)
                await repository_async.nested(nest_post)
                raise Exception("outer rollback")

        # Then - 두 포스트 모두 저장되지 않아야 함
        async with scoped_session_() as verify_sess:
            from tests.helpers.assertions import async_세션에_데이터가_존재하지_않는지_확인

            await async_세션에_데이터가_존재하지_않는지_확인(verify_sess, Post)


class PostRepository(ISessionRepository):
    async def create(self, post: Post, *, session: AsyncSession = None) -> None:
        session.add(post)
        await session.flush()
        await session.refresh(post)

    async def create_error(self, post: Post, *, session: AsyncSession = None) -> None:
        session.add(post)
        raise Exception("error")


class TestAutoSessionAllocate(AsyncBaseTest):
    """자동 세션 할당 테스트"""

    @pytest.mark.asyncio
    async def test_세션이_없을때_자동으로_세션이_할당되는지_확인(self):
        """세션이 없을 때 자동으로 세션이 할당되는지 확인"""
        # Given
        post = self.create_test_post()
        post_repo = PostRepository()

        # When
        await post_repo.create(post)

        # Then
        self.assert_post_saved(post)

    @pytest.mark.asyncio
    async def test_자동_세션_할당에서_오류_발생시_롤백되는지_확인(self):
        """자동 세션 할당에서 오류 발생시 롤백되는지 확인"""
        # Given
        post = self.create_test_post()
        post_repo = PostRepository()

        # When & Then
        with pytest.raises(Exception):
            await post_repo.create_error(post)

        # 포스트가 저장되지 않았는지 확인
        포스트가_저장되지_않았는지_확인(post)
