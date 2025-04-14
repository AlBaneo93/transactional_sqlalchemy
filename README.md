# Transactional-SQLAlchemy

## 개요

### 지원하는 트랜잭션 전파 방식

참조: [Transaction Propagation of Spring framework](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html)

- `REQUIRED` : 이미 트랜잭션이 열린경우 기존의 세션을 사용하거나, 새로운 트랜잭션을 생성
- `REQUIRES_NEW` : 기존 트랜잭션을 무시하고 새롭게 생성
- `NESTED` : 기존 트랜잭션의 자식 트랜잭션을 생성

## 기능

트랜잭션 전파 방식 관리

Auto commit or Rollback (트랜잭션 사용 시)

auto session

동기/비동기 함수 모두 지원

## 사용법

### 1. transactional + auto session

1. 패키지 설치

- ver. sync

```bash
pip install transactional-sqlalchemy
```

- ver. async

```bash
pip install transactional-sqlalchemy[async]
```

2. 세션 핸들러 초기화

```python
from transactional_sqlalchemy import init_manager
from sqlalchemy.ext.asyncio import async_scoped_session

async_scoped_session_ = async_scoped_session(
    async_session_factory, scopefunc=asyncio.current_task
)

init_manager(async_scoped_session_)

```

3. ITransactionalRepository를 상속하는 클래스 작성

- repository 레이어의 클래스 작성시, ITransactionalRepository를 상속
- `session`이라는 이름의 변수가 있는경우 만들어 두었던 세션을 할당

```python
from transactional_sqlalchemy import ITransactionalRepository, transactional

class PostRepository(ITransactionalRepository):
    @transactional # or @transactional(propagation=Propagation.REQUIRES)
    async def requires(self, post: Post, session: AsyncSession) -> None:
        session.add(post)
        ...

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def requires_new(self, post: Post, session: AsyncSession) -> None: ...

    @transactional(propagation=Propagation.NESTED)
    async def nested(self, post: Post, session: AsyncSession) -> None: ...

    async def auto_session_allocate(self, session:AsyncSession) -> None: ...
```

### 2. auto session without transactional

```python
from transactional_sqlalchemy import ISessionRepository


class PostRepository(ISessionRepository):

    async def create(self, post: Post, *, session: AsyncSession = None) -> None: ...
```
