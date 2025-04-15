from enum import Enum


class Propagation(Enum):
    REQUIRES = 'REQUIRES'
    REQUIRES_NEW = 'REQUIRES_NEW'
    NESTED = 'NESTED'
