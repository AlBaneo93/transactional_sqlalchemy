"""
테스트 assertion 헬퍼 함수들
"""


def 포스트가_정상적으로_저장되었는지_확인(post):
    """포스트가 정상적으로 저장되었는지 확인"""
    assert post is not None, "포스트가 None입니다"
    assert post.id is not None, "포스트 ID가 None입니다"


def 포스트가_저장되지_않았는지_확인(post):
    """포스트가 저장되지 않았는지 확인"""
    assert post is not None, "포스트가 None입니다"
    assert post.id is None, "포스트 ID가 존재합니다"


def 모델이_정상적으로_저장되었는지_확인(model):
    """모델이 정상적으로 저장되었는지 확인"""
    assert model is not None, "모델이 None입니다"
    assert model.id is not None, "모델 ID가 None입니다"


def 예외가_발생하는지_확인(exception_class=Exception, match=None):
    """데코레이터: 예외가 발생하는지 확인"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            import pytest

            if match:
                with pytest.raises(exception_class, match=match):
                    return func(*args, **kwargs)
            else:
                with pytest.raises(exception_class):
                    return func(*args, **kwargs)

        return wrapper

    return decorator


def 세션에_데이터가_존재하는지_확인(session, model_class, count=None):
    """세션에 데이터가 존재하는지 확인"""
    from sqlalchemy import select

    stmt = select(model_class)
    result = session.execute(stmt).scalars().all()

    if count is not None:
        assert len(result) == count, f"예상된 개수: {count}, 실제 개수: {len(result)}"
    else:
        assert len(result) > 0, "데이터가 존재하지 않습니다"

    return result


def 세션에_데이터가_존재하지_않는지_확인(session, model_class):
    """세션에 데이터가 존재하지 않는지 확인"""
    from sqlalchemy import select

    stmt = select(model_class)
    result = session.execute(stmt).scalars().all()
    assert len(result) == 0, f"데이터가 존재합니다. 개수: {len(result)}"


async def async_세션에_데이터가_존재하지_않는지_확인(session, model_class):
    """세션에 데이터가 존재하지 않는지 확인"""
    from sqlalchemy import select

    stmt = select(model_class)
    result = await session.execute(stmt)
    result = result.scalars().all()
    assert len(result) == 0, f"데이터가 존재합니다. 개수: {len(result)}"


def 두_포스트가_모두_존재하는지_확인(session, post1, post2):
    """두 포스트가 모두 존재하는지 확인"""
    from sqlalchemy import select

    from tests.conftest import Post

    stmt = select(Post).where(Post.id.in_([post1.id, post2.id]))
    result = session.execute(stmt).scalars().all()
    assert len(result) >= 2, f"두 포스트 중 일부가 존재하지 않습니다. 결과 개수: {len(result)}"


async def async_두_포스트가_모두_존재하는지_확인(session, post1, post2):
    """두 포스트가 모두 존재하는지 확인"""
    from sqlalchemy import select

    from tests.conftest import Post

    stmt = select(Post).where(Post.id.in_([post1.id, post2.id]))
    result = await session.execute(stmt)
    result = result.scalars().all()
    assert len(result) >= 2, f"두 포스트 중 일부가 존재하지 않습니다. 결과 개수: {len(result)}"
