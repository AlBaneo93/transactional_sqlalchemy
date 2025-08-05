import pytest

from transactional_sqlalchemy.domains import Pageable


class TestPageable:
    """Pageable 도메인 객체 테스트"""

    def test_pageable_default_values(self):
        """기본값으로 Pageable 객체 생성 테스트"""
        pageable = Pageable()
        assert pageable.page == 1
        assert pageable.size == 10
        assert pageable.total_items == 0
        assert pageable.total_pages == 0

    def test_pageable_custom_values(self):
        """사용자 정의 값으로 Pageable 객체 생성 테스트"""
        pageable = Pageable(page=2, size=20, total_items=100, total_pages=5)
        assert pageable.page == 2
        assert pageable.size == 20
        assert pageable.total_items == 100
        assert pageable.total_pages == 5

    def test_pageable_limit_property(self):
        """limit 프로퍼티가 size와 동일한지 테스트"""
        pageable = Pageable(size=15)
        assert pageable.limit == 15
        assert pageable.limit == pageable.size

    def test_pageable_offset_property(self):
        """offset 계산이 정확한지 테스트"""
        # 첫 번째 페이지
        pageable1 = Pageable(page=1, size=10)
        assert pageable1.offset == 0

        # 두 번째 페이지
        pageable2 = Pageable(page=2, size=10)
        assert pageable2.offset == 10

        # 세 번째 페이지, 다른 사이즈
        pageable3 = Pageable(page=3, size=20)
        assert pageable3.offset == 40

    def test_pageable_dict_method(self):
        """dict() 메서드가 올바른 딕셔너리를 반환하는지 테스트"""
        pageable = Pageable(page=2, size=15, total_items=50, total_pages=4)
        result = pageable.dict()

        expected = {"page": 2, "size": 15, "total_items": 50, "total_pages": 4}
        assert result == expected
        assert isinstance(result, dict)

    def test_pageable_validate_success(self):
        """유효한 값들에 대해 validate가 성공하는지 테스트"""
        pageable = Pageable(page=1, size=1)
        # 예외가 발생하지 않아야 함
        pageable.validate()

        pageable2 = Pageable(page=10, size=50)
        pageable2.validate()

    def test_pageable_validate_invalid_page_zero(self):
        """page가 0일 때 ValueError가 발생하는지 테스트"""
        pageable = Pageable(page=0, size=10)
        with pytest.raises(ValueError, match="Page number must be greater than or equal to 1"):
            pageable.validate()

    def test_pageable_validate_invalid_page_negative(self):
        """page가 음수일 때 ValueError가 발생하는지 테스트"""
        pageable = Pageable(page=-1, size=10)
        with pytest.raises(ValueError, match="Page number must be greater than or equal to 1"):
            pageable.validate()

    def test_pageable_validate_invalid_size_zero(self):
        """size가 0일 때 ValueError가 발생하는지 테스트"""
        pageable = Pageable(page=1, size=0)
        with pytest.raises(ValueError, match="Page size must be greater than or equal to 1"):
            pageable.validate()

    def test_pageable_validate_invalid_size_negative(self):
        """size가 음수일 때 ValueError가 발생하는지 테스트"""
        pageable = Pageable(page=1, size=-5)
        with pytest.raises(ValueError, match="Page size must be greater than or equal to 1"):
            pageable.validate()

    def test_pageable_frozen_dataclass(self):
        """frozen dataclass로 설정되어 수정이 불가능한지 테스트"""
        pageable = Pageable(page=1, size=10)

        with pytest.raises(AttributeError):
            pageable.page = 2

        with pytest.raises(AttributeError):
            pageable.size = 20

    def test_pageable_metadata(self):
        """field metadata가 올바르게 설정되었는지 테스트"""
        import dataclasses

        fields = dataclasses.fields(Pageable)
        field_dict = {field.name: field for field in fields}

        assert field_dict["page"].metadata["description"] == "현재 페이지 번호"
        assert field_dict["size"].metadata["description"] == "페이지당 항목 수"
        assert field_dict["total_items"].metadata["description"] == "전체 항목 수"
        assert field_dict["total_pages"].metadata["description"] == "전체 페이지 수"
