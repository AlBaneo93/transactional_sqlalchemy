from enum import Enum


class Propagation(Enum):
    REQUIRES = "REQUIRES"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"


class Pageable:
    page: int = 1
    size: int = 10

    def __init__(self, page: int = 1, size: int = 10):
        self.page = page
        self.size = size
