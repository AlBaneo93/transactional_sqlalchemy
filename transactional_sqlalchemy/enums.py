from enum import Enum


class Propagation(str, Enum):
    REQUIRES = "REQUIRES"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"


# TODO 2025-07-30 14:47:16 : 위치 변경 & 상세 구현 필요
# class Entity(ABC):
#     """Base class for all entities."""
#
#     def __post_init__(self):
#         self.validate()
#
#     @abstractmethod
#     def validate(self) -> None:
#         """엔티티의 데이터를 검증합니다.
#
#         이 메서드는 하위 클래스에서 구체적인 검증 규칙을 구현해야 합니다.
#
#         Raises:
#             NotImplementedError: 하위 클래스에서 이 메서드를 구현하지 않은 경우 발생합니다.
#             EntityValidateError: 검증 실패 시 발생합니다.
#         """
#         raise NotImplementedError("Subclasses must implement this method.")


# TODO 2025-07-30 14:47:16 : 위치 변경 & 상세 구현 필요
# @dataclass(frozen=True)
# class BaseFilter(Entity):
#     page: int = 1
#     size: int = 10
#
#     def build_where_conditions(self) -> tuple[list, list]:
#         """동적 WHERE 조건들을 생성합니다.
#         반환값은 (조건 리스트, 조인 리스트) 형태입니다.
#         """
#         conditions = []
#         joins = set()
#         return conditions, list(joins)
#
#     def validate(self) -> None:
#         if self.page < 1:
#             raise ValueError("Page number must be greater than or equal to 1.")
#         if self.size < 1:
#             raise ValueError("Page size must be greater than or equal to 1.")
#
#     def build_datetime_conditions(self, field_: InstrumentedAttribute) -> list:
#         """날짜 범위 검색을 위한 조건을 생성합니다.
#
#         Args:
#             field_ (InstrumentedAttribute): 비교할 모델의 날짜 필드
#
#         Returns:
#             list: 날짜 범위 검색 조건 리스트
#         """
#         conditions = []
#
#         for field_name, field_type in self.__annotations__.items():
#             if field_.name not in field_name:  # Ensure the field is part of the filter
#                 continue
#             if field_type == datetime:
#                 value: datetime = getattr(self, field_name, None)
#                 if value is None:
#                     continue
#
#                 if field_name.startswith("start_"):
#                     conditions.append(field_ >= value)
#                 elif field_name.startswith("end_"):
#                     conditions.append(field_ < (value + timedelta(days=1)))
#
#         return conditions
#
#     @property
#     def limit(self) -> int:
#         return self.size
#
#     @property
#     def offset(self) -> int:
#         return (self.page - 1) * self.size
