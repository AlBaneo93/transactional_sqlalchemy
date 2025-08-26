import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrderItem, UserRolePermission
from transactional_sqlalchemy.repository.base import BaseCRUDRepository


class OrderItemRepository(BaseCRUDRepository[OrderItem]): ...


class UserRolePermissionRepository(BaseCRUDRepository[UserRolePermission]): ...


# 공통 fixture들
@pytest.fixture
def order_item_repository():
    return OrderItemRepository()


@pytest.fixture
def user_role_permission_repository():
    return UserRolePermissionRepository()


@pytest.fixture
async def sample_order_items(transaction_async: AsyncSession):
    """테스트용 OrderItem 데이터 생성"""
    items = [
        OrderItem(order_id=1, product_id=100, quantity=2, price=1000),
        OrderItem(order_id=1, product_id=101, quantity=1, price=2000),
        OrderItem(order_id=2, product_id=100, quantity=3, price=1000),
        OrderItem(order_id=2, product_id=102, quantity=1, price=3000),
    ]
    transaction_async.add_all(items)
    await transaction_async.commit()
    return items


@pytest.fixture
async def sample_permissions(transaction_async: AsyncSession):
    """테스트용 UserRolePermission 데이터 생성"""
    permissions = [
        UserRolePermission(user_id=1, role_id=1, permission_id=1),
        UserRolePermission(user_id=1, role_id=1, permission_id=2),
        UserRolePermission(user_id=1, role_id=2, permission_id=1),
        UserRolePermission(user_id=2, role_id=1, permission_id=1),
    ]
    transaction_async.add_all(permissions)
    await transaction_async.commit()
    return permissions


# ==================== 복합키 조회 테스트 ====================


@pytest.mark.asyncio
async def test_복합키로_모델을_조회한다(order_item_repository, sample_order_items, transaction_async: AsyncSession):
    """복합키 딕셔너리로 모델 조회 테스트"""
    # 딕셔너리 형태로 복합키 조회
    found = await order_item_repository.find_by_id({"order_id": 1, "product_id": 100}, session=transaction_async)

    assert found is not None
    assert found.order_id == 1
    assert found.product_id == 100
    assert found.quantity == 2


@pytest.mark.asyncio
async def test_존재하지_않는_복합키_조회시_none_반환(order_item_repository, transaction_async: AsyncSession):
    """존재하지 않는 복합키 조회 시 None 반환"""
    found = await order_item_repository.find_by_id({"order_id": 999, "product_id": 999}, session=transaction_async)

    assert found is None


@pytest.mark.asyncio
async def test_3개_컬럼_복합키_조회(
    user_role_permission_repository, sample_permissions, transaction_async: AsyncSession
):
    """3개 컬럼으로 구성된 복합키 조회 테스트"""
    found = await user_role_permission_repository.find_by_id(
        {"user_id": 1, "role_id": 1, "permission_id": 2}, session=transaction_async
    )

    assert found is not None
    assert found.user_id == 1
    assert found.role_id == 1
    assert found.permission_id == 2


@pytest.mark.asyncio
async def test_여러_복합키로_모델_목록_조회(order_item_repository, sample_order_items, transaction_async: AsyncSession):
    """여러 복합키로 모델 목록 조회"""
    ids = [
        {"order_id": 1, "product_id": 100},
        {"order_id": 1, "product_id": 101},
        {"order_id": 2, "product_id": 100},
    ]

    results = await order_item_repository.find_all_by_id(ids, session=transaction_async)

    assert len(results) == 3
    # 결과가 올바른지 검증
    found_keys = {(r.order_id, r.product_id) for r in results}
    expected_keys = {(1, 100), (1, 101), (2, 100)}
    assert found_keys == expected_keys


@pytest.mark.asyncio
async def test_빈_복합키_목록_조회시_빈_리스트_반환(order_item_repository, transaction_async: AsyncSession):
    """빈 복합키 목록 조회 시 빈 리스트 반환"""
    results = await order_item_repository.find_all_by_id([], session=transaction_async)
    assert results == []


# ==================== 복합키 존재여부 확인 테스트 ====================


@pytest.mark.asyncio
async def test_복합키_존재여부_확인(order_item_repository, sample_order_items, transaction_async: AsyncSession):
    """복합키로 모델 존재여부 확인"""
    exists = await order_item_repository.exists_by_id({"order_id": 1, "product_id": 100}, session=transaction_async)
    assert exists is True


@pytest.mark.asyncio
async def test_존재하지_않는_복합키_존재여부는_false(order_item_repository, transaction_async: AsyncSession):
    """존재하지 않는 복합키 존재여부는 False"""
    exists = await order_item_repository.exists_by_id({"order_id": 999, "product_id": 999}, session=transaction_async)
    assert exists is False


# ==================== 복합키 저장 테스트 ====================


@pytest.mark.asyncio
async def test_복합키_모델_새로_저장(order_item_repository, transaction_async: AsyncSession):
    """복합키 모델 새로 저장"""
    new_item = OrderItem(order_id=3, product_id=200, quantity=5, price=1500)
    saved = await order_item_repository.save(new_item, session=transaction_async)

    assert saved is not None
    assert saved.order_id == 3
    assert saved.product_id == 200
    assert saved.quantity == 5


@pytest.mark.asyncio
async def test_복합키_모델_업데이트(order_item_repository, sample_order_items, transaction_async: AsyncSession):
    """기존 복합키 모델 업데이트"""
    # 기존 데이터 조회
    existing = await order_item_repository.find_by_id({"order_id": 1, "product_id": 100}, session=transaction_async)

    # 수량 변경
    existing.quantity = 10
    existing.price = 5000

    # 저장 (업데이트)
    saved = await order_item_repository.save(existing, session=transaction_async)

    assert saved.quantity == 10
    assert saved.price == 5000

    # DB에서 다시 조회하여 확인
    updated = await order_item_repository.find_by_id({"order_id": 1, "product_id": 100}, session=transaction_async)
    assert updated.quantity == 10
    assert updated.price == 5000


# ==================== 복합키 개수 조회 테스트 ====================


@pytest.mark.asyncio
async def test_복합키_모델_전체_개수_조회(order_item_repository, sample_order_items, transaction_async: AsyncSession):
    """복합키 모델 전체 개수 조회"""
    count = await order_item_repository.count(session=transaction_async)
    assert count >= 2


# ==================== 복합키 내부 메서드 테스트 ====================


# def test_복합키_컬럼_목록_반환(order_item_repository):
#     """복합키 컬럼 목록 반환 확인"""
#     pk_columns = order_item_repository._BaseCRUDRepository__get_pk_columns()
#     assert len(pk_columns) == 2
#     column_names = {col.name for col in pk_columns}
#     assert column_names == {"order_id", "product_id"}


# def test_3개_복합키_컬럼_목록_반환(user_role_permission_repository):
#     """3개 컬럼 복합키 컬럼 목록 반환 확인"""
#     pk_columns = user_role_permission_repository._BaseCRUDRepository__get_pk_columns()
#     assert len(pk_columns) == 3
#     column_names = {col.name for col in pk_columns}
#     assert column_names == {"user_id", "role_id", "permission_id"}


def test_복합키_여부_확인(order_item_repository):
    """복합키 여부 확인"""
    assert not order_item_repository._is_single_pk()


# def test_복합키_모델에서_키값_추출(order_item_repository):
#     """복합키 모델에서 키값 추출 테스트"""
#     item = OrderItem(order_id=1, product_id=100, quantity=2)
#     pk_values = order_item_repository._BaseCRUDRepository__get_pk_values_from_model(item)
#
#     assert isinstance(pk_values, dict)
#     assert pk_values == {"order_id": 1, "product_id": 100}


# def test_복합키_모든_값_존재여부_확인(order_item_repository):
#     """복합키 모든 값 존재여부 확인"""
#     # 모든 값 존재
#     pk_values = {"order_id": 1, "product_id": 100}
#     assert order_item_repository._BaseCRUDRepository__has_all_pk_values(pk_values) is True
#
#     # 일부 값 누락
#     pk_values_partial = {"order_id": 1, "product_id": None}
#     assert order_item_repository._BaseCRUDRepository__has_all_pk_values(pk_values_partial) is False


# ==================== 에러 케이스 테스트 ====================


@pytest.mark.asyncio
async def test_복합키_딕셔너리_누락_컬럼_에러(order_item_repository, transaction_async: AsyncSession):
    """복합키에서 필수 컬럼 누락 시 에러"""
    with pytest.raises(ValueError, match="Missing primary key value for column"):
        await order_item_repository.find_by_id(
            {"order_id": 1},  # product_id 누락
            session=transaction_async,
        )


@pytest.mark.asyncio
async def test_복합키에_딕셔너리가_아닌_값_전달시_에러(order_item_repository, transaction_async: AsyncSession):
    """복합키에 딕셔너리가 아닌 값 전달 시 에러"""
    with pytest.raises(ValueError, match="Composite primary key must be a dictionary"):
        await order_item_repository.find_by_id(123, session=transaction_async)


# @pytest.mark.asyncio
# async def test_단일키에_딕셔너리_전달시_에러():
#     """단일키에 딕셔너리 전달 시 에러 (기존 TestModel 사용)"""
#     from tests.conftest import SampleModel
#
#     class TestRepo(BaseCRUDRepository[SampleModel]): ...
#
#     repo = TestRepo()
#
#     # 단일키에 딕셔너리 전달하면 에러
#     with pytest.raises(ValueError, match="Single primary key should not be a dictionary"):
#         repo._BaseCRUDRepository__build_pk_condition({"id": 1})


# def test_복합키_조건_생성(order_item_repository):
#     """복합키 조건 생성 테스트"""
#     pk_dict = {"order_id": 1, "product_id": 100}
#     condition = order_item_repository._BaseCRUDRepository__build_pk_condition(pk_dict)
#
#     # 조건이 생성되는지 확인 (SQLAlchemy ColumnElement인지)
#     from sqlalchemy.sql.elements import ColumnElement
#
#     assert isinstance(condition, ColumnElement)
