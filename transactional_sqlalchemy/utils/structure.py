from typing import Generic, TypeVar

# 스택에 저장될 데이터 타입을 나타내는 TypeVar를 정의합니다.
T = TypeVar("T")


class Stack(Generic[T]):
    """제네릭 스택 자료구조 구현체.

    LIFO(Last In, First Out) 원칙에 따라 동작하는 스택을 구현합니다.

    Args:
        Generic[T]: 스택에 저장할 데이터 타입
    """

    def __init__(self) -> None:
        # 내부 리스트가 T 타입의 요소만 포함하도록 지정합니다.
        self._items: list[T] = []

    def push(self, item: T) -> None:
        """스택의 맨 위에 항목을 추가합니다.

        Args:
            item (T): 스택에 추가할 항목
        """
        self._items.append(item)

    def pop(self) -> T:
        """스택의 맨 위 항목을 제거하고 반환합니다.

        Returns:
            T: 스택의 맨 위 항목

        Raises:
            IndexError: 스택이 비어있을 때
        """
        if not self.is_empty():
            return self._items.pop()
        raise IndexError("pop from empty stack")

    def peek(self) -> T:
        """스택의 맨 위 항목을 제거하지 않고 반환합니다.

        Returns:
            T: 스택의 맨 위 항목

        Raises:
            IndexError: 스택이 비어있을 때
        """
        if not self.is_empty():
            return self._items[-1]
        raise IndexError("peek from empty stack")

    def is_empty(self) -> bool:
        """스택이 비어있는지 확인합니다.

        Returns:
            bool: 스택이 비어있으면 True, 그렇지 않으면 False
        """
        return not self._items

    def size(self) -> int:
        """스택에 있는 항목의 수를 반환합니다.

        Returns:
            int: 스택에 저장된 항목의 개수
        """
        return len(self._items)

    def __len__(self) -> int:
        """len() 함수를 사용할 수 있도록 합니다.

        Returns:
            int: 스택에 저장된 항목의 개수
        """
        return self.size()
