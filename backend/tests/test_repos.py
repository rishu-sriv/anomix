"""
Repository integration tests — run against the real `finpulse_test` database.

These tests use the `db_session` fixture from conftest.py.  Each test is
wrapped in a rolled-back transaction so no data leaks between tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import AnomalyType, ReportStatus, Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _candle(time: datetime, volume: int = 1_000_000) -> dict:
    return {
        "time": time,
        "ticker": "TSLA",
        "open": Decimal("180.0000"),
        "high": Decimal("181.0000"),
        "low": Decimal("179.0000"),
        "close": Decimal("180.5000"),
        "volume": volume,
    }


def _anomaly_data(**overrides) -> dict:
    base = {
        "id": uuid.uuid4(),
        "detected_at": datetime.now(tz=timezone.utc),
        "candle_time": datetime.now(tz=timezone.utc),
        "ticker": "TSLA",
        "type": AnomalyType.volume_spike,
        "severity": Severity.HIGH,
        "zscore": 4.5,
        "iqr_flag": False,
        "report_status": ReportStatus.pending,
    }
    base.update(overrides)
    return base


# ── MarketRepo ────────────────────────────────────────────────────────────────


async def test_upsert_candles_inserts_new_rows(db_session: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    candles = [
        _candle(now.replace(minute=0)),
        _candle(now.replace(minute=1)),
        _candle(now.replace(minute=2)),
    ]
    inserted = await MarketRepo.upsert_candles(db_session, candles)
    assert inserted == 3


async def test_upsert_candles_ignores_duplicates(db_session: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    candle = [_candle(now)]

    first = await MarketRepo.upsert_candles(db_session, candle)
    assert first == 1

    # Same (time, ticker) composite PK — must be a no-op
    second = await MarketRepo.upsert_candles(db_session, candle)
    assert second == 0


# ── AnomalyRepo ───────────────────────────────────────────────────────────────


async def test_create_anomaly_and_retrieve_by_id(db_session: AsyncSession) -> None:
    data = _anomaly_data()
    created = await AnomalyRepo.create(db_session, data)

    assert created.id == data["id"]
    assert created.ticker == "TSLA"
    assert created.severity == Severity.HIGH

    fetched = await AnomalyRepo.get_by_id(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.zscore == pytest.approx(4.5)


async def test_update_report_status(db_session: AsyncSession) -> None:
    anomaly = await AnomalyRepo.create(db_session, _anomaly_data())
    assert anomaly.report_status == ReportStatus.pending

    await AnomalyRepo.update_report_status(
        db_session, anomaly.id, ReportStatus.completed
    )

    updated = await AnomalyRepo.get_by_id(db_session, anomaly.id)
    assert updated is not None
    assert updated.report_status == ReportStatus.completed


# ── ReportRepo ────────────────────────────────────────────────────────────────


async def test_create_report_linked_to_anomaly(db_session: AsyncSession) -> None:
    anomaly = await AnomalyRepo.create(db_session, _anomaly_data())

    report_data = {
        "id": uuid.uuid4(),
        "anomaly_id": anomaly.id,
        "summary": "Test volume spike summary.",
        "reasons": ["Volume exceeded 2.5σ.", "Short-term liquidity event."],
        "risk_level": "Medium",
        "confidence": 0.82,
        "tokens_used": 0,
        "latency_ms": 5,
        "created_at": datetime.now(tz=timezone.utc),
    }
    report = await ReportRepo.create(db_session, report_data)
    assert report.anomaly_id == anomaly.id

    fetched = await ReportRepo.get_by_anomaly_id(db_session, anomaly.id)
    assert fetched is not None
    assert fetched.id == report.id
    assert fetched.confidence == pytest.approx(0.82)
    assert "Volume exceeded 2.5σ." in fetched.reasons
