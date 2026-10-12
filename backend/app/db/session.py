from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.models.base import Base


def create_app_engine(url: str | None = None) -> Engine:
    if not url:
        return create_sqlite_engine()
    if url.startswith("sqlite"):
        return create_sqlite_engine(url)
    return create_engine(url, pool_pre_ping=True)


def create_sqlite_engine(url: str = "sqlite+pysqlite:///./erp_dev.sqlite") -> Engine:
    connect_args = {"check_same_thread": False}
    kwargs = {"connect_args": connect_args}
    if url.endswith(":memory:"):
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
