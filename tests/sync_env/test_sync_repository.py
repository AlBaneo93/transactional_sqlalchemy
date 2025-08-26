"""
동기 환경 트랜잭션 리포지토리 테스트
"""

import logging
from inspect import iscoroutinefunction

import pytest
from sqlalchemy.orm import Session, scoped_session

from tests.conftest import Post
from tests.factories.post_factory import PostFactory

# PostFactory 인스턴스 생성
from tests.helpers.assertions import (
    두_포스트가_모두_존재하는지_확인,
    포스트가_저장되지_않았는지_확인,
)
from transactional_sqlalchemy import (
    ISessionRepository,
    ITransactionalRepository,
    Propagation,
    transaction_context,
    transactional,
)
from transactional_sqlalchemy.utils.structure import Stack

from ..helpers.base_test import SyncBaseTest

post_factory = PostFactory()


class TransactionSyncRepositoryImpl(ITransactionalRepository):
    @transactional(propagation=Propagation.REQUIRES)
    def requires(self, post: Post, *, session: Session):
        session.add(post)
        session.flush()

    @transactional(propagation=Propagation.REQUIRES)
    def requires_error(self, post: Post, *, session: Session):
        session.add(post)
        raise Exception("requires error")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    def requires_new(self, post: Post, *, session: Session):
        session.add(post)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    def requires_new_error(self, post: Post, *, session: Session):
        session.add(post)
        raise Exception("tests")

    @transactional(propagation=Propagation.NESTED)
    def nested(self, post: Post, *, session: Session):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        return post

    @transactional(propagation=Propagation.NESTED)
    def nested_error(self, post: Post, *, session: Session):
        # 내부 트랜잭션에서 실행, 외부에는 영향 주지 않음
        session.add(post)
        raise Exception("tests")  # rollback

    @transactional
    def default(self, post: Post, *, session: Session):
        # 정상적으로 DB 저장이 되는지 확인
        session.add(post)
        # session.commit()
        # session.refresh(post)
        #
        # assert post.id is not None


@pytest.fixture(scope="function", autouse=True)
def repository_sync() -> TransactionSyncRepositoryImpl:
    repo = TransactionSyncRepositoryImpl()
    return repo


class TestSyncTransactional(SyncBaseTest):
    """동기 기본 트랜잭션 테스트"""

    def test_기본_트랜잭션이_정상적으로_작동하는지_확인(
        self, repository_sync: TransactionSyncRepositoryImpl, transaction_sync
    ):
        """기본 트랜잭션 데코레이터가 정상적으로 작동하는지 확인"""
        # Given
        post = self.create_test_post()

        # When
        repository_sync.default(post)

        # Then
        self.assert_post_saved(post)


class TestSyncRequiresNewTransactional(SyncBaseTest):
    """동기 REQUIRES_NEW 트랜잭션 전파 테스트"""

    def test_requires_new_전파가_새로운_트랜잭션으로_실행되는지_확인(self, repository_sync, transaction_sync):
        """REQUIRES_NEW 전파가 새로운 트랜잭션에서 실행되는지 확인"""
        # Given
        post = self.create_test_post()
        new_post = self.create_new_post()

        with transaction_sync as sess:
            # 외부 트랜잭션에 포스트 추가
            self.add_post_to_session_and_flush(post, session=sess)

            # When - 새로운 트랜잭션에서 실행
            repository_sync.requires_new(new_post)

            # 외부 트랜잭션 커밋
            sess.commit()

        # Then - 두 포스트 모두 저장되어야 함
        self.assert_post_saved(new_post)
        self.assert_post_saved(post)

        with transaction_sync as sess:
            sess.delete(post)
            sess.delete(new_post)
            sess.commit()

    def test_requires_new_전파에서_오류_발생시_외부_트랜잭션은_정상_커밋되는지_확인(
        self, repository_sync, transaction_sync
    ):
        """REQUIRES_NEW 전파에서 오류 발생시 외부 트랜잭션은 정상 커밋되는지 확인"""
        # Given
        post = self.create_test_post()
        new_post = self.create_new_post()

        sess = transaction_sync
        # 외부 트랜잭션에 포스트 추가
        self.add_post_to_session_and_flush(post, session=sess)

        # When & Then - 새로운 트랜잭션에서 오류 발생
        with pytest.raises(Exception):
            logging.info(f"코루틴 함수 여부: {iscoroutinefunction(repository_sync.requires_new_error)}")
            repository_sync.requires_new_error(new_post)

        # Then - 새로운 포스트는 저장되지 않았지만 외부 포스트는 저장되어야 함
        self.assert_post_not_saved(new_post)


class TestSyncRequiresTransactional(SyncBaseTest):
    """동기 REQUIRES 트랜잭션 전파 테스트"""

    def test_requires_전파가_정상적으로_세션을_생성하고_저장하는지_확인(self, repository_sync, transaction_sync):
        """REQUIRES 전파가 정상적으로 세션을 생성하고 저장하는지 확인"""
        # Given - 외부 세션이 없는 상황
        post = self.create_test_post()

        # When
        repository_sync.requires(post)

        # Then
        self.assert_post_saved(post)

        with transaction_sync as sess:
            sess.delete(post)
            sess.commit()

    def test_requires_전파에서_오류_발생시_롤백되는지_확인(self, repository_sync):
        """REQUIRES 전파에서 오류 발생시 롤백되는지 확인"""
        # Given
        post = self.create_test_post()

        # When & Then
        with pytest.raises(Exception):
            repository_sync.requires_error(post)

        # 포스트가 저장되지 않았는지 확인
        포스트가_저장되지_않았는지_확인(post)


class TestSyncNestedTransactional(SyncBaseTest):
    """동기 NESTED 트랜잭션 전파 테스트"""

    def test_nested_전파가_외부와_내부_모두_정상_저장되는지_확인(
        self,
        repository_sync,
        transaction_sync,
        scoped_session_: scoped_session,
    ):
        """NESTED 전파가 외부와 내부 모두 정상 저장되는지 확인"""
        # Given
        post = self.create_test_post()
        nest_post = post_factory.create_nested_test_post()

        with transaction_sync as sess:
            # 외부 트랜잭션에 포스트 추가
            self.add_post_to_session_and_flush(post, session=sess)

            # When - 중첩 트랜잭션 실행
            repository_sync.nested(nest_post)

            # 외부 트랜잭션 커밋
            sess.commit()

        # Then - 두 포스트 모두 저장되어야 함
        self.assert_post_saved(post)

        # 새로운 세션에서 두 포스트 모두 조회되는지 확인
        with scoped_session_() as sess:
            두_포스트가_모두_존재하는지_확인(sess, post, nest_post)

        # 테스트에서 추가된 데이터 삭제
        with scoped_session_() as sess:
            sess.delete(nest_post)
            sess.delete(post)
            sess.commit()

    def test_nested_전파에서_내부_오류시_외부는_정상_커밋되는지_확인(self, repository_sync, transaction_sync):
        """NESTED 전파에서 내부 오류시 외부는 정상 커밋되는지 확인"""
        # Given
        post = self.create_test_post()
        nest_post = post_factory.create_nested_test_post()

        with transaction_sync as sess:
            # 외부 트랜잭션에 포스트 추가
            self.add_post_to_session_and_flush(post, session=sess)

            # When & Then - 중첩 트랜잭션에서 오류 발생
            with pytest.raises(Exception):
                repository_sync.nested_error(nest_post)

            # 외부 트랜잭션은 정상 커밋되어야 함
            sess.flush()
            sess.refresh(post)

            # Then - 외부 포스트만 저장되고 중첩 포스트는 저장되지 않아야 함
            self.assert_post_saved(post)
            포스트가_저장되지_않았는지_확인(nest_post)

        with transaction_sync as sess:
            sess.delete(post)
            sess.commit()

    def test_nested_전파에서_외부_오류시_모두_롤백되는지_확인(
        self,
        repository_sync,
        scoped_session_: scoped_session,
        session_start_up,
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

        post = self.create_test_post()
        nest_post = post_factory.create_nested_test_post()

        sess_ = transaction_context.get()
        assert sess is not None

        # When & Then - 외부 트랜잭션에서 오류 발생
        with pytest.raises(Exception, match="outer rollback"):
            with sess_.peek() as sess:
                self.add_post_to_session_and_flush(post, session=sess)
                repository_sync.nested(nest_post)
                raise Exception("outer rollback")

        # Then - 두 포스트 모두 저장되지 않아야 함
        with scoped_session_() as verify_sess:
            from tests.helpers.assertions import 세션에_데이터가_존재하지_않는지_확인

            세션에_데이터가_존재하지_않는지_확인(verify_sess, Post)


class PostRepository(ISessionRepository):
    def create(self, post: Post, *, session: Session = None) -> None:
        session.add(post)
        session.flush()
        session.refresh(post)
        # session.close()

    def create_error(self, post: Post, *, session: Session = None) -> None:
        session.add(post)
        raise Exception("error")


class TestAutoSessionAllocate(SyncBaseTest):
    """동기 자동 세션 할당 테스트"""

    def test_세션이_없을때_자동으로_세션이_할당되는지_확인(self):
        """세션이 없을 때 자동으로 세션이 할당되는지 확인"""
        # Given
        post = self.create_test_post()
        post_repo = PostRepository()

        # When
        post_repo.create(post)

        # Then
        self.assert_post_saved(post)

    def test_자동_세션_할당에서_오류_발생시_롤백되는지_확인(self):
        """자동 세션 할당에서 오류 발생시 롤백되는지 확인"""
        # Given
        post = self.create_test_post()
        post_repo = PostRepository()

        # When & Then
        with pytest.raises(Exception):
            post_repo.create_error(post)

        # 포스트가 저장되지 않았는지 확인
        포스트가_저장되지_않았는지_확인(post)
