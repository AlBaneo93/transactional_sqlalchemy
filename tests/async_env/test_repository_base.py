import pytest
from sqlalchemy import Column, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from tests.async_env.conftest import TestModel
from tests.conftest import ORMBase
from transactional_sqlalchemy.enums import Pageable
from transactional_sqlalchemy.repository.base import BaseCRUDRepository


class TestModelRepository(BaseCRUDRepository[TestModel]): ...


# 공통 fixture: BaseCRUDRepository 인스턴스 생성
@pytest.fixture
def repository():
    return TestModelRepository(TestModel)


@pytest.mark.asyncio
async def test_아이디로_존재하는_모델을_조회한다(repository, transaction_async: AsyncSession):
    # 사전 데이터 준비
    model = TestModel(name="test")
    transaction_async.add(model)
    await transaction_async.commit()

    # 테스트
    found = await repository.find_by_id(model.id, session=transaction_async)
    assert found is not None
    assert found.id == model.id


@pytest.mark.asyncio
async def test_존재하지_않는_아이디_조회시_none_반환(repository, transaction_async: AsyncSession):
    found = await repository.find_by_id(999999, session=transaction_async)
    assert found is None


@pytest.mark.asyncio
async def test_모든_모델을_조회한다(repository, transaction_async: AsyncSession):
    # 데이터 준비
    models = [TestModel(name=f"name{i}") for i in range(3)]
    transaction_async.add_all(models)
    await transaction_async.commit()

    results = await repository.find_all(session=transaction_async)
    assert len(results) >= 3


@pytest.mark.asyncio
async def test_페이징_기능이_동작한다(repository, transaction_async: AsyncSession):
    models = [TestModel(name=f"name{i}") for i in range(10)]
    transaction_async.add_all(models)
    await transaction_async.commit()

    pageable = Pageable(page=0, size=5)
    results = await repository.find_all(pageable=pageable, session=transaction_async)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_여러_아이디로_모델_목록을_조회한다(repository, transaction_async: AsyncSession):
    models = [TestModel(name=f"name{i}") for i in range(3)]
    transaction_async.add_all(models)
    await transaction_async.commit()

    ids = [m.id for m in models]
    results = await repository.find_all_by_id(ids, session=transaction_async)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_빈_아이디_목록_조회시_빈_리스트_반환(repository, transaction_async: AsyncSession):
    results = await repository.find_all_by_id([], session=transaction_async)
    assert results == []


@pytest.mark.asyncio
async def test_모델을_저장한다(repository, transaction_async: AsyncSession):
    model = TestModel(name="save_test")
    saved = await repository.save(model, session=transaction_async)
    assert saved is not None


@pytest.mark.asyncio
async def test_여러_모델을_저장한다(repository, transaction_async: AsyncSession):
    models = [TestModel(name=f"batch{i}") for i in range(3)]
    saved = await repository.save_all(models, session=transaction_async)
    assert all(m is not None for m in saved)


@pytest.mark.asyncio
async def test_아이디_존재여부를_확인한다(repository, transaction_async: AsyncSession):
    model = TestModel(name="exists_test")
    transaction_async.add(model)
    await transaction_async.commit()

    exists = await repository.exists_by_id(model.id, session=transaction_async)
    assert exists is True


@pytest.mark.asyncio
async def test_존재하지_않는_아이디_존재여부는_false(repository, transaction_async: AsyncSession):
    exists = await repository.exists_by_id(999999, session=transaction_async)
    assert exists is False


@pytest.mark.asyncio
async def test_모델_전체_개수를_조회한다(repository, transaction_async: AsyncSession):
    count = await repository.count(session=transaction_async)
    assert isinstance(count, int)


def test_기본키_컬럼_단일_반환(repository):
    pk = repository._BaseCRUDRepository__get_pk_columns()
    assert pk.name == "id"


def test_복합_기본키가_있으면_에러_발생():
    class MultiPKModel(ORMBase):
        __tablename__ = "multipk"
        id1 = Column(Integer, primary_key=True)
        id2 = Column(Integer, primary_key=True)

    repo = BaseCRUDRepository(MultiPKModel)
    import pytest

    with pytest.raises(ValueError):
        repo._BaseCRUDRepository__get_pk_columns()
