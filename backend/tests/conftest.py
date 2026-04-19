"""
Test fixtures for FinPulse.

Strategy:
- A session-scoped `test_engine` creates the `finpulse_test` database once,
  builds all tables from SQLAlchemy metadata, and converts market_data to a
  hypertable.  Dropped at the end of the test session.
- A function-scoped `db_session` wraps each test in a transaction that is
  rolled back after the test, keeping tests fully isolated from each other.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base

TEST_DB_NAME = "finpulse_test"


# ── Event loop (session-scoped so async fixtures can share it) ────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Test database (created once per session, dropped on teardown) ─────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    from app.config import settings  # deferred so env vars are resolved at fixture time

    # Build URLs — swap the DB name in/out
    base_url = settings.async_database_url
    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    test_url = base_url.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

    # Create the test DB (connect to postgres admin DB to do this)
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await admin_engine.dispose()

    # Connect to the test DB and build schema
    engine = create_async_engine(test_url, echo=False)
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
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    await admin_engine.dispose()


# ── Per-test session with rollback isolation ──────────────────────────────

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Each test gets a fresh AsyncSession.  The session is rolled back after
    the test so no data leaks between tests.
    """
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
