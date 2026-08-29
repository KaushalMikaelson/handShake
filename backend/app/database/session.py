"""SQLAlchemy engine/session wiring.

Postgres is the target (docker-compose) because we rely on real DB-level
constraints - notably the uniqueness constraint on webhook event_id that makes
duplicate-delivery handling correct by construction rather than by convention.
SQLite is supported for zero-dependency local runs and tests; it enforces the
same UNIQUE constraint.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables and seed demo data if the catalog is empty."""
    from app import models  # noqa: F401  (register mappers)
    from app.services.seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
