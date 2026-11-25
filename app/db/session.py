"""数据库会话工厂。生产走 DATABASE_URL（PostgreSQL 16），测试落 sqlite 内存库，
两端 SQL 由 SQLAlchemy 2 统一生成。"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import load_settings
from app.db.base import Base

_engine = None
_session_factory = None


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _pool_kwargs(url: str) -> dict:
    """内存 sqlite 必须共用同一个连接，否则建表与查询会落在不同库。"""
    if url.startswith("sqlite") and ":memory:" in url:
        return {"poolclass": StaticPool}
    return {}


def init_engine(database_url: str | None = None):
    """幂等创建引擎；测试可在建表前调用。"""
    global _engine, _session_factory
    url = database_url or load_settings().database_url
    if _engine is not None and str(_engine.url) == url:
        return _engine
    _engine = create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args=_connect_args(url),
        **_pool_kwargs(url),
    )
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def create_all(database_url: str | None = None) -> None:
    engine = init_engine(database_url)
    Base.metadata.create_all(engine)


def get_session_factory():
    if _session_factory is None:
        init_engine()
    return _session_factory


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()

