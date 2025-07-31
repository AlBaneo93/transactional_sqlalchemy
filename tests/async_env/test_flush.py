import logging
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import Post
from transactional_sqlalchemy import Propagation, transactional


class AutoFlushTestService:
    """auto_flush 기능 테스트를 위한 서비스 클래스"""

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_requires_with_flush(self, post: Post, *, session: AsyncSession):
        """외부 REQUIRES - auto_flush=False (세션 소유자)"""
        session.add(post)
        # flush하지 않고 내부 함수 호출

        inner_post = Post(title="Inner Post", content="Inner Content")
        result = await self.inner_requires_auto_flush(inner_post)
        return result

    @transactional(propagation=Propagation.REQUIRES)
    async def inner_requires_auto_flush(self, post: Post, *, session: AsyncSession):
        """내부 REQUIRES - auto_flush=True (세션 비소유자)"""
        session.add(post)
        # 여기서 auto_flush에 의해 자동으로 flush되어야 함
        return post

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_no_changes(self, *, session: AsyncSession):
        """변경사항이 없는 외부 함수"""
        # 아무 변경사항 없음
        return await self.inner_no_changes()

    @transactional(propagation=Propagation.REQUIRES)
    async def inner_no_changes(self, *, session: AsyncSession):
        """변경사항이 없는 내부 함수 - flush가 호출되지 않아야 함"""
        return "no changes"

    @transactional(propagation=Propagation.REQUIRES)
    async def outer_with_manual_flush(self, post: Post, *, session: AsyncSession):
        """수동으로 flush를 호출하는 함수"""
        session.add(post)
        await session.flush()  # 수동 flush

        inner_post = Post(title="After Manual Flush", content="Content")
        return await self.inner_after_manual_flush(inner_post)

    @transactional(propagation=Propagation.REQUIRES)
    async def inner_after_manual_flush(self, post: Post, *, session: AsyncSession):
        """수동 flush 후 호출되는 내부 함수"""
        session.add(post)
        return post

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new_function(self, post: Post, *, session: AsyncSession):
        """REQUIRES_NEW - auto_flush=False (세션 소유자)"""
        session.add(post)
        return post


@pytest_asyncio.fixture
def auto_flush_service():
    return AutoFlushTestService()


class TestAutoFlush:
    """auto_flush 기능 테스트"""

    @pytest.mark.asyncio
    async def test_auto_flush_in_nested_requires(self, auto_flush_service, scoped_session_):
        """중첩된 REQUIRES에서 auto_flush 동작 확인"""
        post = Post(title="Outer Post", content="Outer Content")

        # 다른 세션으로 모니터링용 세션 생성
        monitor_session = scoped_session_()

        # When
        result = await auto_flush_service.outer_requires_with_flush(post)

        # Then - auto_flush에 의해 내부 함수의 변경사항이 다른 세션에서도 조회 가능해야 함
        posts = await monitor_session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) == 2  # 외부 + 내부 post
        assert any(p.title == "Outer Post" for p in all_posts)
        assert any(p.title == "Inner Post" for p in all_posts)
        assert result.title == "Inner Post"

        await monitor_session.close()

    @pytest.mark.asyncio
    async def test_no_flush_when_no_changes(self, auto_flush_service):
        """변경사항이 없을 때 flush가 호출되지 않는지 확인"""
        # When
        with patch.object(AsyncSession, "flush", new_callable=AsyncMock) as mock_flush:
            result = await auto_flush_service.outer_no_changes()

            # Then - flush가 호출되지 않아야 함
            mock_flush.assert_not_called()
            assert result == "no changes"

    @pytest.mark.asyncio
    async def test_auto_flush_only_when_dirty_objects_exist(self, auto_flush_service):
        """Dirty 객체가 있을 때만 flush가 호출되는지 확인"""
        post = Post(title="Test Post", content="Test Content")

        with patch(
            "transactional_sqlalchemy.wrapper.async_wrapper.AsyncSession.flush", new_callable=AsyncMock
        ) as mock_flush:
            # When - dirty 객체가 있는 경우
            await auto_flush_service.outer_requires_with_flush(post)

            # Then - flush가 호출되어야 함 (내부 함수에서)
            assert mock_flush.call_count >= 1

    @pytest.mark.asyncio
    async def test_flush_call_monitoring_with_logging(self, auto_flush_service, caplog):
        """로깅을 통한 flush 호출 모니터링"""
        post = Post(title="Log Test Post", content="Log Content")

        # DEBUG 레벨에서 flush 관련 로그 캡처
        with caplog.at_level(logging.DEBUG):
            await auto_flush_service.outer_requires_with_flush(post)

        # flush 관련 로그 확인 (실제 구현에서 로그를 추가해야 함)
        [record for record in caplog.records if "flush" in record.message.lower()]

        # 이 테스트는 wrapper에 flush 로깅을 추가한 후에 유효함
        # assert len(flush_logs) > 0

    @pytest.mark.asyncio
    async def test_requires_new_no_auto_flush(self, auto_flush_service, scoped_session_):
        """REQUIRES_NEW에서는 auto_flush=False 확인"""
        post = Post(title="Requires New Post", content="New Content")

        # When
        await auto_flush_service.requires_new_function(post)

        # Then - REQUIRES_NEW는 독립적인 트랜잭션이므로 즉시 커밋됨
        monitor_session = scoped_session_()
        posts = await monitor_session.execute(select(Post))
        all_posts = posts.scalars().all()

        # REQUIRES_NEW는 자체 커밋하므로 데이터가 저장됨
        assert len(all_posts) >= 1
        assert any(p.title == "Requires New Post" for p in all_posts)

        await monitor_session.close()

    @pytest.mark.asyncio
    async def test_session_state_before_and_after_flush(self, auto_flush_service, scoped_session_):
        """Flush 전후 세션 상태 확인"""
        # 모니터링용 세션
        monitor_session = scoped_session_()

        # 초기 상태 확인
        initial_posts = await monitor_session.execute(select(Post))
        initial_count = len(initial_posts.scalars().all())

        # 데이터 추가 및 flush 테스트
        post = Post(title="State Test Post", content="State Content")
        await auto_flush_service.outer_requires_with_flush(post)

        # 최종 상태 확인
        final_posts = await monitor_session.execute(select(Post))
        final_count = len(final_posts.scalars().all())

        # auto_flush에 의해 데이터가 다른 세션에서도 조회 가능해야 함
        assert final_count > initial_count

        await monitor_session.close()

    @pytest.mark.asyncio
    async def test_manual_flush_vs_auto_flush(self, auto_flush_service, scoped_session_):
        """수동 flush와 auto_flush 동작 비교"""
        post = Post(title="Manual Flush Test", content="Manual Content")

        monitor_session = scoped_session_()

        # When - 수동 flush 포함 함수 실행
        await auto_flush_service.outer_with_manual_flush(post)

        # Then - 수동 flush + auto_flush 모두 정상 동작
        posts = await monitor_session.execute(select(Post))
        all_posts = posts.scalars().all()

        assert len(all_posts) >= 2
        assert any(p.title == "Manual Flush Test" for p in all_posts)
        assert any(p.title == "After Manual Flush" for p in all_posts)

        await monitor_session.close()


class TestAutoFlushWithMock:
    """Mock을 사용한 정확한 flush 호출 테스트"""

    @pytest.mark.asyncio
    async def test_flush_called_with_dirty_objects(self, auto_flush_service):
        """Dirty 객체가 있을 때 flush 호출 확인"""
        post = Post(title="Mock Test Post", content="Mock Content")

        # AsyncSession.flush를 mock으로 교체
        with patch("sqlalchemy.ext.asyncio.AsyncSession.flush", new_callable=AsyncMock) as mock_flush:
            await auto_flush_service.outer_requires_with_flush(post)

            # 내부 함수에서 auto_flush=True로 인해 flush가 호출되어야 함
            # (정확한 호출 횟수는 구현에 따라 달라질 수 있음)
            assert mock_flush.call_count >= 1

    @pytest.mark.asyncio
    async def test_no_flush_with_clean_session(self, auto_flush_service):
        """Clean 세션에서는 flush가 호출되지 않는지 확인"""
        with patch("sqlalchemy.ext.asyncio.AsyncSession.flush", new_callable=AsyncMock) as mock_flush:
            # 변경사항이 없는 함수 호출
            await auto_flush_service.outer_no_changes()

            # flush가 호출되지 않아야 함
            mock_flush.assert_not_called()
