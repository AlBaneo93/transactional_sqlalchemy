import sys
from dataclasses import asdict, dataclass, field
from enum import Enum

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Direction(str, Enum):
    ASC = "asc"
    DESC = "desc"

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        # value를 소문자로 변환합니다.
        value = str(value).lower()

        # 소문자로 변환된 값과 일치하는 멤버를 찾습니다.
        for member in cls:
            if member.value == value:
                return member

        # 일치하는 멤버가 없으면 None을 반환하여 FastAPI가 오류를 처리하게 합니다.
        return None


# 2. 단일 정렬 조건을 나타내는 데이터클래스
@dataclass(frozen=True)
class Order:
    field: str
    direction: Direction


class Sort:
    def __init__(self, orders: list[Order]):
        self._orders = orders

    @classmethod
    def by(cls, direction: Direction, field: str) -> Self:
        """첫 번째 정렬 조건을 생성합니다."""
        return cls([Order(field=field, direction=direction)])

    def and_(self, other: Self) -> Self:
        """기존 정렬 조건에 새로운 정렬 조건을 추가합니다. (and는 키워드라 and_ 사용)"""
        # 새로운 리스트를 만들어 불변성을 유지하고 체이닝이 가능하게 함
        new_orders = self._orders + other._orders
        return Sort(new_orders)

    def __iter__(self):
        """for order in sort: 처럼 반복문을 사용할 수 있게 합니다."""
        return iter(self._orders)

    def __repr__(self) -> str:
        """객체를 보기 좋게 출력하기 위함입니다."""
        order_str = ", ".join([f"{o.field} {o.direction.name}" for o in self._orders])
        return f"Sort({order_str})"


@dataclass
class Pageable:
    page: int = field(default=1, init=True, metadata={"description": "현재 페이지 번호"})
    size: int = field(default=10, init=True, metadata={"description": "페이지당 항목 수"})
    total_items: int = field(default=0, metadata={"description": "전체 항목 수"})
    total_pages: int = field(default=0, init=False, metadata={"description": "전체 페이지 수"})

    sort: Sort | None = field(default=None, metadata={"description": "정렬 조건"})

    def validate(self):
        if self.page < 1:
            raise ValueError("Page number must be greater than or equal to 1.")
        if self.size < 1:
            raise ValueError("Page size must be greater than or equal to 1.")

    def dict(self) -> dict:
        return asdict(self)

    def __post_init__(self):
        # 2. total_pages를 계산합니다.
        if self.total_items > 0 and self.size > 0:
            import math

            self.total_pages = math.ceil(self.total_items / self.size)
        else:
            self.total_pages = 0  # 아이템이 없으면 페이지도 0

    @property
    def limit(self) -> int:
        return self.size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    # @property
    # def order_by(self) :
    #     """
    #     정렬 조건을 반환합니다.
    #     정렬 조건이 없으면 None을 반환합니다.
    #     """
    #     for order in self.sort:
    #         if order.direction == Direction.ASC:
    #             yield f"{order.field} ASC"
    #         else:
    #             yield f"{order.field} DESC"
    #     return self.sort if self.sort else None


class PageRequest:
    @staticmethod
    def of(page: int = 1, size: int = 10, sort: Sort = None) -> Pageable:
        """
        페이지 요청을 생성합니다.

        Args:
            page (int): 페이지 번호 (기본값: 1)
            size (int): 페이지당 항목 수 (기본값: 10)

        Returns:
            Pageable: 페이지 요청 객체
        """
        return Pageable(page=page, size=size, sort=sort)
