"""
Test fixtures for FinPulse.

Strategy:
- A session-scoped `test_engine` creates the `finpulse_test` database once,
  builds all tables from SQLAlchemy metadata, and converts market_data to a
  hypertable.  Dropped at the end of the test session.
- A function-scoped `db_session` wraps each test in a transaction that is
  rolled back after the test, keeping tests fully isolated from each other.

Connection pooling:
  NullPool is used for the test engine so that each AsyncSession gets a
  brand-new asyncpg connection instead of reusing a pooled one.  This
  prevents asyncpg "Future attached to a different loop" and
  "another operation is in progress" errors that occur when pool
  connections are shared across tests that run in sequential event-loop
  iterations.

Event loop:
  asyncio_mode = auto  +  asyncio_default_fixture_loop_scope = session
  in pytest.ini mean all async fixtures share a single session-scoped event
  loop automatically — no manual event_loop fixture needed.
  (Requires pytest-asyncio >= 0.24.0, pinned in requirements.txt.)
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.models import Base

TEST_DB_NAME = "finpulse_test"


# ── Test database (created once per session, dropped on teardown) ─────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    from app.config import settings  # deferred so env vars are resolved at fixture time

    # Build URLs — swap the DB name in/out
    base_url = settings.async_database_url
    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    test_url = base_url.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

    # Create the test DB (connect to postgres admin DB to do this)
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await admin_engine.dispose()

    # Connect to the test DB and build schema
    # NullPool: each connection is created and destroyed per-use, eliminating
    # cross-test asyncpg Future lifecycle issues.
    engine = create_async_engine(test_url, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        # Enable TimescaleDB extension first
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        # Create all tables from SQLAlchemy models
        await conn.run_sync(Base.metadata.create_all)
        # Convert market_data to a hypertable (mirrors production setup)
        await conn.execute(
            text(
                "SELECT create_hypertable('market_data', 'time',"
                " chunk_time_interval => INTERVAL '1 day',"
                " if_not_exists => TRUE)"
            )
        )

    yield engine

    # Teardown — drop the test DB
    await engine.dispose()
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin_engine.connect() as conn:
        # Terminate any lingering connections (e.g. from db_session fixtures
        # whose close() failed because the event loop was already winding down)
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                f" WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()"
            )
        )
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin_engine.dispose()


# ── Per-test session with rollback isolation ──────────────────────────────

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Each test gets a fresh AsyncSession backed by a NullPool connection.
    The session is rolled back after the test so no data leaks between tests.

    Teardown uses try/except rather than awaiting rollback directly: with
    pytest-asyncio's session-scoped event loop, the loop may begin winding
    down before function-scoped fixture finalizers run, causing asyncpg to
    raise "Future attached to a different loop".  NullPool guarantees the
    underlying connection is discarded on close, so PostgreSQL rolls back
    any uncommitted transaction automatically — the explicit rollback call
    is just belt-and-suspenders and is safe to suppress on failure.
    """
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    session = session_factory()
    try:
        yield session
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        try:
            await session.close()
        except Exception:
            pass
