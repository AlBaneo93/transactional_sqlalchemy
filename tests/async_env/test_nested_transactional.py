import logging

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Post
from transactional_sqlalchemy import (
    Propagation,
    transactional,
)
from transactional_sqlalchemy.utils.transaction_util import (
    get_session_stack_size,
)


class NestedTransactionalService:
    """중첩된 transactional 테스트를 위한 서비스 클래스"""

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_requires(self, post: Post, *, session: AsyncSession):
        """외부 REQUIRES 트랜잭션"""
        session.add(post)
        await session.flush()

        # ✅ 올바른 사용법: session은 데코레이터가 자동 주입
        inner_post = Post(title="Inner Post", content="Inner Content")
        return await self.inner_requires(inner_post)

    @transactional(propagation=Propagation.REQUIRES)
    async def inner_requires(self, post: Post, *, session: AsyncSession):
        """내부 REQUIRES 트랜잭션 - 같은 세션 사용해야 함"""
        session.add(post)
        await session.flush()

        # 세션 스택 크기 확인
        stack_size = get_session_stack_size()
        logging.info(f"Inner REQUIRES - Stack size: {stack_size}")

        return post

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_requires_with_new(self, post: Post, *, session: AsyncSession):
        """외부 REQUIRES + 내부 REQUIRES_NEW"""
        session.add(post)
        await session.flush()

        # ✅ REQUIRES_NEW도 자동 주입
        inner_post = Post(title="Inner New Post", content="Inner New Content")
        return await self.inner_requires_new(inner_post)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def inner_requires_new(self, post: Post, *, session: AsyncSession):
        """내부 REQUIRES_NEW 트랜잭션 - 새로운 세션 사용"""
        session.add(post)
        await session.flush()

        stack_size = get_session_stack_size()
        logging.info(f"Inner REQUIRES_NEW - Stack size: {stack_size}")

        return post

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_requires_with_nested(self, post: Post, *, session: AsyncSession):
        """외부 REQUIRES + 내부 NESTED"""
        session.add(post)
        await session.flush()

        # ✅ NESTED도 자동 주입
        inner_post = Post(title="Inner Nested Post", content="Inner Nested Content")
        return await self.inner_nested(inner_post)

    @transactional(propagation=Propagation.NESTED)
    async def inner_nested(self, post: Post, *, session: AsyncSession):
        """내부 NESTED 트랜잭션 - savepoint 사용"""
        session.add(post)
        await session.flush()

        stack_size = get_session_stack_size()
        logging.info(f"Inner NESTED - Stack size: {stack_size}")

        return post

    # 에러 시나리오
    @transactional(propagation=Propagation.REQUIRES)
    async def outer_with_inner_error(self, post: Post, *, session: AsyncSession):
        """외부는 성공, 내부에서 에러 발생"""
        session.add(post)
        await session.flush()

        inner_post = Post(title="Error Post", content="Error Content")
        await self.inner_with_error(inner_post)  # ✅ session 자동 주입

    @transactional(propagation=Propagation.REQUIRES)
    async def inner_with_error(self, post: Post, *, session: AsyncSession):
        """의도적으로 에러를 발생시키는 내부 함수"""
        session.add(post)
        await session.flush()
        raise Exception("Inner transaction error")

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_with_new_error(self, post: Post, *, session: AsyncSession):
        """외부는 성공, 내부 REQUIRES_NEW에서 에러"""
        session.add(post)
        await session.flush()

        inner_post = Post(title="New Error Post", content="New Error Content")
        await self.inner_new_with_error(inner_post)  # ✅ session 자동 주입

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def inner_new_with_error(self, post: Post, *, session: AsyncSession):
        """REQUIRES_NEW에서 에러 발생"""
        session.add(post)
        await session.flush()
        raise Exception("Inner REQUIRES_NEW error")

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_with_nested_error(self, post: Post, *, session: AsyncSession):
        """외부는 성공, 내부 NESTED에서 에러"""
        session.add(post)
        await session.flush()

        inner_post = Post(title="Nested Error Post", content="Nested Error Content")
        try:
            await self.inner_nested_with_error(inner_post)  # ✅ session 자동 주입
        except Exception:
            # NESTED 에러는 외부에 영향 없어야 함
            pass

        return post

    @transactional(propagation=Propagation.NESTED)
    async def inner_nested_with_error(self, post: Post, *, session: AsyncSession):
        """NESTED에서 에러 발생"""
        session.add(post)
        await session.flush()
        raise Exception("Inner NESTED error")

    # 복잡한 3단계 중첩
    @transactional(propagation=Propagation.REQUIRES)
    async def three_level_outer(self, post: Post, *, session: AsyncSession):
        """3단계 중첩의 최외부"""
        session.add(post)
        await session.flush()

        middle_post = Post(title="Middle Post", content="Middle Content")
        return await self.three_level_middle(middle_post)  # ✅ session 자동 주입

    @transactional(propagation=Propagation.REQUIRES)
    async def three_level_middle(self, post: Post, *, session: AsyncSession):
        """3단계 중첩의 중간"""
        session.add(post)
        await session.flush()

        inner_post = Post(title="Inner Post", content="Inner Content")
        return await self.three_level_inner(inner_post)  # ✅ session 자동 주입

    @transactional(propagation=Propagation.NESTED)
    async def three_level_inner(self, post: Post, *, session: AsyncSession):
        """3단계 중첩의 최내부"""
        session.add(post)
        await session.flush()

        stack_size = get_session_stack_size()
        logging.info(f"Three level inner - Stack size: {stack_size}")

        return post


@pytest_asyncio.fixture
def nested_service():
    return NestedTransactionalService()


class TestNestedTransactional:
    """중첩된 transactional 데코레이터 테스트"""

    async def test_requires_nested_success(self, nested_service, scoped_session_):
        """REQUIRES 중첩 호출 성공 케이스"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When
        result = await nested_service.outer_requires(post)

        # Then
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) == 2  # 외부 + 내부 post
        assert any(p.title == "Outer Post" for p in all_posts)
        assert any(p.title == "Inner Post" for p in all_posts)
        assert result.title == "Inner Post"

    async def test_requires_with_requires_new(self, nested_service, scoped_session_):
        """REQUIRES + REQUIRES_NEW 중첩"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When
        result = await nested_service.outer_requires_with_new(post)

        # Then
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        # REQUIRES_NEW는 독립적으로 커밋되므로 두 post 모두 저장
        assert len(all_posts) == 2
        assert result.title == "Inner New Post"

    async def test_requires_with_nested(self, nested_service, scoped_session_):
        """REQUIRES + NESTED 중첩"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When
        result = await nested_service.outer_requires_with_nested(post)

        # Then
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) == 2
        assert result.title == "Inner Nested Post"

    async def test_inner_error_rollback(self, nested_service, scoped_session_):
        """내부 트랜잭션 에러 시 전체 롤백"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When/Then
        with pytest.raises(Exception, match="Inner transaction error"):
            await nested_service.outer_with_inner_error(post)

        # 전체 롤백되어야 함
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) == 0

    async def test_requires_new_error_isolation(self, nested_service, scoped_session_):
        """REQUIRES_NEW 에러 시 외부 트랜잭션과 격리"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When/Then
        with pytest.raises(Exception, match="Inner REQUIRES_NEW error"):
            await nested_service.outer_with_new_error(post)

        # 외부 트랜잭션은 롤백되지만, REQUIRES_NEW는 별도 처리
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        # 구현에 따라 달라질 수 있음 - 외부만 롤백되거나 전체 롤백
        assert len(all_posts) == 0

    async def test_nested_error_isolation(self, nested_service, scoped_session_):
        """NESTED 에러 시 savepoint만 롤백"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When
        await nested_service.outer_with_nested_error(post)

        # Then
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        # 외부 트랜잭션만 성공해야 함
        assert len(all_posts) == 1
        assert all_posts[0].title == "Outer Post"

    async def test_three_level_nesting(self, nested_service, scoped_session_):
        """3단계 중첩 트랜잭션"""
        # Given
        post = Post(title="Outer Post", content="Outer Content")

        # When
        result = await nested_service.three_level_outer(post)

        # Then
        session = scoped_session_()
        posts = await session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) == 3  # 외부 + 중간 + 내부
        assert result.title == "Inner Post"

    async def test_session_stack_management(self, nested_service):
        """세션 스택 관리 테스트"""
        # 초기 스택 크기
        initial_size = get_session_stack_size()

        # 트랜잭션 실행
        post = Post(title="Test Post", content="Test Content")
        await nested_service.outer_requires(post)

        # 실행 후 스택 크기 (원복되어야 함)
        final_size = get_session_stack_size()
        assert initial_size == final_size

    @pytest.mark.asyncio
    async def test_transaction_depth_tracking(self, nested_service, caplog):
        """트랜잭션 깊이 추적 테스트"""
        post = Post(title="Test Post", content="Test Content")

        # caplog를 사용하여 로그 캡처
        with caplog.at_level(logging.INFO):
            await nested_service.three_level_outer(post)

        # 로그에서 스택 크기 정보 확인
        stack_logs = [record for record in caplog.records if "Stack size" in record.message]
        assert len(stack_logs) > 0

        # 추가 검증: 로그 내용 확인
        for log_record in stack_logs:
            print(f"Log: {log_record.message}")  # 디버깅용
            assert "Stack size" in log_record.message

    @pytest.mark.asyncio
    async def test_transaction_depth_tracking_detailed(self, nested_service, caplog):
        """상세한 트랜잭션 깊이 추적 테스트"""
        post = Post(title="Test Post", content="Test Content")

        # INFO 레벨 이상의 로그 캡처
        with caplog.at_level(logging.INFO):
            await nested_service.three_level_outer(post)

        # 스택 크기 로그 확인
        stack_logs = [record for record in caplog.records if "Stack size" in record.message]

        # 최소 1개 이상의 스택 크기 로그가 있어야 함
        assert len(stack_logs) > 0

        # 각 로그의 스택 크기 추출 및 검증
        stack_sizes = []
        for record in stack_logs:
            # "Three level inner - Stack size: 3" 형태에서 숫자 추출
            message = record.message
            if "Stack size:" in message:
                size_str = message.split("Stack size:")[-1].strip()
                try:
                    size = int(size_str)
                    stack_sizes.append(size)
                except ValueError:
                    pass

        # 스택 크기가 올바르게 기록되었는지 확인
        assert len(stack_sizes) > 0
        assert all(size > 0 for size in stack_sizes)

        # 로그 메시지 내용도 확인
        log_messages = [record.message for record in caplog.records]
        assert any("Three level inner" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logging_in_different_propagations(self, nested_service, caplog):
        """다양한 전파 레벨에서 로깅 테스트"""
        post = Post(title="Logging Test", content="Logging Content")

        with caplog.at_level(logging.INFO):
            # REQUIRES 테스트
            await nested_service.outer_requires(post)

            # REQUIRES_NEW 테스트
            await nested_service.outer_requires_with_new(post)

            # NESTED 테스트
            await nested_service.outer_requires_with_nested(post)

        # 각 전파 레벨별 로그 확인
        requires_logs = [r for r in caplog.records if "Inner REQUIRES" in r.message]
        requires_new_logs = [r for r in caplog.records if "Inner REQUIRES_NEW" in r.message]
        nested_logs = [r for r in caplog.records if "Inner NESTED" in r.message]

        assert len(requires_logs) > 0
        assert len(requires_new_logs) > 0
        assert len(nested_logs) > 0
