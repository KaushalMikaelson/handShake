"""Test fixtures.

Each test gets an isolated on-disk SQLite database so the real DB-level
constraints (notably the unique index on processed_webhook_events.event_id)
are exercised - an in-memory stand-in or a mocked session would test the mock,
not the constraint that actually protects us.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

TMP = Path("/tmp/agent_commerce_tests")
TMP.mkdir(exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TMP}/default.db")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")
# Deliberately no ANTHROPIC_API_KEY / RAZORPAY_KEY_ID: the suite runs against
# the deterministic paths, so results are reproducible and offline.


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"


# Set TEST_DATABASE_URL to a Postgres URL to run the whole suite against the
# real deployment database. This matters: SQLite does not enforce foreign keys
# by default, so a Postgres run is what actually verifies the constraints the
# duplicate-webhook and idempotency guarantees rest on.
#
#   TEST_DATABASE_URL=postgresql+psycopg2://agent:agent@127.0.0.1:5432/agent_commerce_test \
#     .venv/bin/python -m pytest ../tests
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def db(db_path):
    """A fresh, seeded database session."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from app.database.session import Base
    from app import models  # noqa: F401
    from app.services.seed import seed_if_empty

    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        Base.metadata.drop_all(bind=engine)
    else:
        engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )

        # SQLite ignores foreign keys unless asked; turn them on so a local run
        # catches the same referential bugs a Postgres run would.
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    seed_if_empty(session)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def buyer(db):
    from app.config import settings
    from app.models import Buyer

    return db.get(Buyer, settings.demo_buyer_id)


@pytest.fixture
def merchant(db):
    from sqlalchemy import select

    from app.models import Merchant

    return db.scalar(select(Merchant))


@pytest.fixture
def payments():
    """The shared payment client, with call counters reset per test."""
    from app.payments.razorpay_service import get_payment_client

    client = get_payment_client()
    client.reset_counters()
    yield client
    client.reset_counters()
