from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Pageable:
    page: int = field(default=1, init=True, metadata={"description": "현재 페이지 번호"})
    size: int = field(default=10, init=True, metadata={"description": "페이지당 항목 수"})
    total_items: int = field(default=0, metadata={"description": "전체 항목 수"})
    total_pages: int = field(default=0, metadata={"description": "전체 페이지 수"})

    def validate(self):
        if self.page < 1:
            raise ValueError("Page number must be greater than or equal to 1.")
        if self.size < 1:
            raise ValueError("Page size must be greater than or equal to 1.")

    def dict(self) -> dict:
        return asdict(self)

    @property
    def limit(self) -> int:
        return self.size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
