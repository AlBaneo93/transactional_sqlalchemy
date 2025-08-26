from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from transactional_sqlalchemy import BaseCRUDRepository


# 모든 모델이 상속받을 Base 클래스
class Base(DeclarativeBase):
    pass


# --- 기본 모델들 ---


class Galaxy(Base):  # 원본: User
    __tablename__ = "galaxy"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50))  # 원본: name

    star_systems: Mapped[list[StarSystem]] = relationship(back_populates="galaxy")


class Asteroid(Base):  # 원본: File
    __tablename__ = "asteroid"
    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(100))  # 원본: filename

    belts: Mapped[list[AsteroidBelt]] = relationship(back_populates="asteroid")


class Orbit(Base):  # 원본: Thread
    __tablename__ = "orbit"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(200))  # 원본: title

    star_system: Mapped[StarSystem] = relationship(back_populates="orbit")
    comets: Mapped[list[Comet]] = relationship(back_populates="orbit")
    belts: Mapped[list[AsteroidBelt]] = relationship(back_populates="orbit")


class Planet(Base):  # 원본: Document
    __tablename__ = "planet"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255))  # 원본: title

    star_system: Mapped[StarSystem] = relationship(back_populates="planet")
    moons: Mapped[list[Moon]] = relationship(back_populates="planet")


# --- 연결 모델 및 하위 모델들 ---


class Moon(Base):  # 원본: DocNode
    __tablename__ = "moon"
    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(String(1000))  # 원본: content
    planet_id: Mapped[int] = mapped_column(ForeignKey("planet.id"))

    planet: Mapped[Planet] = relationship(back_populates="moons")


class Comet(Base):  # 원본: Query
    __tablename__ = "comet"
    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(String(1000))  # 원본: message
    orbit_id: Mapped[int] = mapped_column(ForeignKey("orbit.id"))

    orbit: Mapped[Orbit] = relationship(back_populates="comets")


class AsteroidBelt(Base):  # 원본: ThreadFile
    __tablename__ = "asteroid_belt"
    orbit_id: Mapped[int] = mapped_column(ForeignKey("orbit.id"), primary_key=True)
    asteroid_id: Mapped[int] = mapped_column(ForeignKey("asteroid.id"), primary_key=True)

    orbit: Mapped[Orbit] = relationship(back_populates="belts")
    asteroid: Mapped[Asteroid] = relationship(back_populates="belts")


# --- 핵심 모델 ---


class StarSystem(Base):  # 원본: Library
    __tablename__ = "star_system"
    id: Mapped[int] = mapped_column(primary_key=True)

    # 외래 키 필드
    galaxy_id: Mapped[int] = mapped_column(ForeignKey("galaxy.id"))
    planet_id: Mapped[int] = mapped_column(ForeignKey("planet.id"), unique=True)
    orbit_id: Mapped[int] = mapped_column(ForeignKey("orbit.id"), unique=True)

    # 관계
    galaxy: Mapped[Galaxy] = relationship(back_populates="star_systems")
    planet: Mapped[Planet] = relationship(back_populates="star_system")
    orbit: Mapped[Orbit] = relationship(back_populates="star_system")


class StarSystemRepository(BaseCRUDRepository[StarSystem]): ...
