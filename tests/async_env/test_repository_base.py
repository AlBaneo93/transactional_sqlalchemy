"""
비동기 환경 기본 리포지토리 테스트
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import SampleModel
from transactional_sqlalchemy.repository.base import BaseCRUDRepository

from ..helpers.base_test import AsyncBaseTest


class SampleModelRepository(BaseCRUDRepository[SampleModel]): ...


# 공통 fixture: BaseCRUDRepository 인스턴스 생성
@pytest.fixture
def repository():
    return SampleModelRepository()


class TestAsyncBaseRepository(AsyncBaseTest):
    """비동기 기본 리포지토리 테스트"""

    @pytest.mark.asyncio
    async def test_아이디로_존재하는_모델을_조회한다(self, repository, transaction_async: AsyncSession):
        """ID로 존재하는 모델을 조회할 수 있는지 확인"""
        # Given - 테스트 데이터 준비
        model = self.create_sample_model(name="test")
        transaction_async.add(model)
        await transaction_async.commit()

        # When
        found = await repository.find_by_id(model.id, session=transaction_async)

        # Then
        assert found is not None
        assert found.id == model.id

    @pytest.mark.asyncio
    async def test_존재하지_않는_아이디_조회시_none_반환(self, repository, transaction_async: AsyncSession):
        """존재하지 않는 ID 조회 시 None을 반환하는지 확인"""
        # When
        found = await repository.find_by_id(999999, session=transaction_async)

        # Then
        assert found is None

    @pytest.mark.asyncio
    async def test_모든_모델을_조회한다(self, repository, transaction_async: AsyncSession):
        """모든 모델을 조회할 수 있는지 확인"""
        # Given - 데이터 준비
        models = [self.create_sample_model(name=f"name{i}") for i in range(3)]
        transaction_async.add_all(models)
        await transaction_async.commit()

        # When
        results = await repository.find_all(session=transaction_async)

        # Then
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_페이징_기능이_동작한다(self, repository, transaction_async: AsyncSession):
        """페이징 기능이 정상적으로 동작하는지 확인"""
        # Given
        total_count = 10
        models = [self.create_sample_model(name=f"name{i}") for i in range(total_count)]
        transaction_async.add_all(models)
        await transaction_async.commit()

        # When
        results = await repository.find_all(session=transaction_async)

        # Then
        assert len(results) == total_count

    @pytest.mark.asyncio
    async def test_여러_아이디로_모델_목록을_조회한다(self, repository, transaction_async: AsyncSession):
        """여러 ID로 모델 목록을 조회할 수 있는지 확인"""
        # Given
        models = [self.create_sample_model(name=f"name{i}") for i in range(3)]
        transaction_async.add_all(models)
        await transaction_async.commit()

        # When
        ids = [m.id for m in models]
        results = await repository.find_all_by_id(ids, session=transaction_async)

        # Then
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_빈_아이디_목록_조회시_빈_리스트_반환(self, repository, transaction_async: AsyncSession):
        """빈 ID 목록 조회 시 빈 리스트를 반환하는지 확인"""
        # When
        results = await repository.find_all_by_id([], session=transaction_async)

        # Then
        assert results == []

    @pytest.mark.asyncio
    async def test_모델을_저장한다(self, repository, transaction_async: AsyncSession):
        """모델을 정상적으로 저장할 수 있는지 확인"""
        # Given
        model = self.create_sample_model(name="save_test")

        # When
        saved = await repository.save(model, session=transaction_async)

        # Then
        assert saved is not None
        self.assert_model_saved(saved)

    @pytest.mark.asyncio
    async def test_아이디_존재여부를_확인한다(self, repository, transaction_async: AsyncSession):
        """ID 존재여부를 올바르게 확인하는지 테스트"""
        # Given
        model = self.create_sample_model(name="exists_test")
        transaction_async.add(model)
        await transaction_async.commit()

        # When & Then
        exists = await repository.exists_by_id(model.id, session=transaction_async)
        assert exists is True

    @pytest.mark.asyncio
    async def test_존재하지_않는_아이디_존재여부는_false(self, repository, transaction_async: AsyncSession):
        """존재하지 않는 ID의 존재여부 확인 시 False를 반환하는지 확인"""
        # When
        exists = await repository.exists_by_id(999999, session=transaction_async)

        # Then
        assert exists is False

    @pytest.mark.asyncio
    async def test_모델_전체_개수를_조회한다(self, repository, transaction_async: AsyncSession):
        """모델 전체 개수를 올바르게 조회하는지 확인"""
        # When
        count = await repository.count(session=transaction_async)

        # Then
        assert isinstance(count, int)
