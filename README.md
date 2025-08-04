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

### 3. 기본 CRUD Repository 사용

패키지에서 제공하는 기본 CRUD Repository 클래스를 상속하여 빠르게 Repository를 구현할 수 있습니다.

#### BaseCRUDRepository

기본적인 CRUD 연산을 제공하는 베이스 클래스입니다.

```python
from transactional_sqlalchemy import BaseCRUDRepository
from sqlalchemy.ext.asyncio import AsyncSession
from your_models import User

class UserRepository(BaseCRUDRepository[User]):
    pass  # 기본 CRUD 메서드들이 자동으로 사용 가능

# 사용 예시
user_repo = UserRepository()

# 기본 제공 메서드들
user = await user_repo.find_by_id(1, session=session)
users = await user_repo.find_all(session=session)
saved_user = await user_repo.save(new_user, session=session)
exists = await user_repo.exists_by_id(1, session=session)
count = await user_repo.count(session=session)
```

**제공되는 메서드:**

- `find_by_id(id, *, session)`: ID로 단일 모델 조회
- `find(where=None, *, session)`: 조건으로 단일 모델 조회
- `find_all(*, pageable=None, where=None, session)`: 전체 모델 조회 (페이징 지원)
- `find_all_by_id(ids, *, session)`: 여러 ID로 모델들 조회
- `save(model, *, session)`: 모델 저장/업데이트 (upsert)
- `exists(where=None, *, session)`: 모델 존재 여부 확인
- `exists_by_id(id, *, where=None, session)`: ID로 존재 여부 확인
- `count(*, where=None, session)`: 모델 개수 조회

#### BaseCRUDTransactionRepository

`BaseCRUDRepository`에 자동 트랜잭션 관리 기능이 추가된 클래스입니다.

```python
from transactional_sqlalchemy import BaseCRUDTransactionRepository, Propagation
from your_models import User

class UserTransactionRepository(BaseCRUDTransactionRepository[User]):
    # 모든 메서드에 자동으로 @transactional 데코레이터가 적용됩니다
    pass

# 사용 예시
user_repo = UserTransactionRepository()

# 트랜잭션이 자동으로 관리됩니다
user = await user_repo.find_by_id(1)  # session 매개변수 불필요
saved_user = await user_repo.save(new_user)  # 자동 커밋/롤백
```

#### 조건부 조회와 페이징

```python
from sqlalchemy import and_
from transactional_sqlalchemy import Pageable

# where 조건 사용
active_users = await user_repo.find_all(
    where=and_(User.is_active == True, User.age >= 18),
    session=session
)

# 페이징 사용
pageable = Pageable(offset=0, limit=10)
users_page = await user_repo.find_all(
    pageable=pageable,
    session=session
)

# 조건부 개수 조회
adult_count = await user_repo.count(
    where=User.age >= 18,
    session=session
)
```

#### 커스텀 메서드 추가

```python
class UserRepository(BaseCRUDTransactionRepository[User]):

    @transactional(propagation=Propagation.REQUIRES)
    async def find_by_email(self, email: str, *, session: AsyncSession) -> User | None:
        return await self.find(where=User.email == email, session=session)

    @transactional(propagation=Propagation.REQUIRES)
    async def create_user_with_profile(self, user_data: dict, profile_data: dict, *, session: AsyncSession) -> User:
        # 복잡한 비즈니스 로직
        user = User(**user_data)
        saved_user = await self.save(user, session=session)

        profile = UserProfile(user_id=saved_user.id, **profile_data)
        session.add(profile)

        return saved_user
```

#### 고급 사용 예시

```python
from sqlalchemy import or_, desc
from transactional_sqlalchemy import BaseCRUDTransactionRepository, Propagation

class UserService(BaseCRUDTransactionRepository[User]):

    @transactional(propagation=Propagation.REQUIRES)
    async def search_users(self, keyword: str, *, session: AsyncSession) -> list[User]:
        """이름 또는 이메일로 사용자 검색"""
        return await self.find_all(
            where=or_(
                User.name.ilike(f"%{keyword}%"),
                User.email.ilike(f"%{keyword}%")
            ),
            session=session
        )

    @transactional(propagation=Propagation.REQUIRES)
    async def get_user_stats(self, *, session: AsyncSession) -> dict:
        """사용자 통계 조회"""
        total_users = await self.count(session=session)
        active_users = await self.count(where=User.is_active == True, session=session)

        return {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users
        }

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def deactivate_user(self, user_id: int, *, session: AsyncSession) -> User:
        """사용자 비활성화 (새로운 트랜잭션)"""
        user = await self.find_by_id(user_id, session=session)
        if not user:
            raise ValueError("User not found")

        user.is_active = False
        return await self.save(user, session=session)
```
