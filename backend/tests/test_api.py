"""
API endpoint integration tests.

Strategy:
- Build a lightweight test FastAPI app WITHOUT the production lifespan
  (avoids needing a production DB connection during test startup).
- Override the get_db dependency to inject the test session from conftest.py.
- Each test gets a fresh session that is rolled back after the test.
- Seed data with repo methods directly — same session, same transaction.

Endpoints covered:
  GET /api/v1/health
  GET /api/v1/stocks/{ticker}/candles
  GET /api/v1/anomalies
  GET /api/v1/reports/{anomaly_id}  — 404, 202 (pending), 200 (completed)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as v1_router
from app.core.database import get_db
from app.models.anomaly import AnomalyType, ReportStatus, Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo

pytestmark = pytest.mark.asyncio


# ── Test app factory ──────────────────────────────────────────────────────────


def _build_test_app(session: AsyncSession) -> FastAPI:
    """
    Create a FastAPI app that uses the given test session for every request.

    No lifespan — avoids connecting to the production DB during test setup.
    The router is mounted fresh for each test client so dependency overrides
    don't bleed between tests.
    """
    _app = FastAPI()

    async def _override_get_db():
        yield session

    _app.dependency_overrides[get_db] = _override_get_db
    _app.include_router(v1_router)
    return _app


# ── Client fixture ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    _app = _build_test_app(db_session)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helper builders ───────────────────────────────────────────────────────────


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


def _report_data(anomaly_id: uuid.UUID) -> dict:
    return {
        "id": uuid.uuid4(),
        "anomaly_id": anomaly_id,
        "summary": "Unusual volume spike detected.",
        "reasons": ["Volume exceeded 2.5σ above rolling mean."],
        "risk_level": "Medium",
        "confidence": 0.82,
        "tokens_used": 0,
        "latency_ms": 5,
        "created_at": datetime.now(tz=timezone.utc),
    }


# ── Health ────────────────────────────────────────────────────────────────────


async def test_health_returns_200(client: httpx.AsyncClient) -> None:
    """Health endpoint always returns 200 — status may be degraded if Redis is down."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("healthy", "degraded")
    assert body["db"] in ("ok", "error")
    assert "anomalies_24h" in body


# ── Stocks / candles ──────────────────────────────────────────────────────────


async def test_candles_empty_when_no_data(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/stocks/TSLA/candles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["has_more"] is False
    assert body["ticker"] == "TSLA"


async def test_candles_returns_inserted_rows(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    candles = [_candle(now.replace(minute=i)) for i in range(3)]
    await MarketRepo.upsert_candles(db_session, candles)
    await db_session.flush()

    resp = await client.get("/api/v1/stocks/TSLA/candles", params={"hours": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 3
    assert body["ticker"] == "TSLA"
    # Each candle has the expected fields
    assert set(body["data"][0].keys()) == {"time", "ticker", "open", "high", "low", "close", "volume"}


async def test_candles_rejects_invalid_interval(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/stocks/TSLA/candles", params={"interval": "2h"})
    assert resp.status_code == 422


# ── Anomalies ─────────────────────────────────────────────────────────────────


async def test_anomalies_empty_list(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/anomalies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["has_more"] is False
    assert body["next_cursor"] is None


async def test_anomalies_returns_seeded_row(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    anomaly = await AnomalyRepo.create(db_session, _anomaly_data())
    await db_session.flush()

    resp = await client.get("/api/v1/anomalies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(anomaly.id)
    assert body["data"][0]["severity"] == "HIGH"
    assert body["data"][0]["type"] == "volume_spike"
    assert body["data"][0]["report_status"] == "pending"


async def test_anomalies_filter_by_severity(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await AnomalyRepo.create(db_session, _anomaly_data(severity=Severity.HIGH))
    await AnomalyRepo.create(db_session, _anomaly_data(severity=Severity.MEDIUM))
    await db_session.flush()

    resp = await client.get("/api/v1/anomalies", params={"severity": "HIGH"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["severity"] == "HIGH"


async def test_anomalies_filter_by_ticker(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await AnomalyRepo.create(db_session, _anomaly_data(ticker="TSLA"))
    await AnomalyRepo.create(db_session, _anomaly_data(ticker="AAPL"))
    await db_session.flush()

    resp = await client.get("/api/v1/anomalies", params={"ticker": "TSLA"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["ticker"] == "TSLA"


# ── Reports ───────────────────────────────────────────────────────────────────


async def test_report_404_for_nonexistent_anomaly(client: httpx.AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/reports/{fake_id}")
    assert resp.status_code == 404
    assert resp.json()["error"] == "report_not_found"


async def test_report_202_pending(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    anomaly = await AnomalyRepo.create(
        db_session, _anomaly_data(report_status=ReportStatus.pending)
    )
    await db_session.flush()

    resp = await client.get(f"/api/v1/reports/{anomaly.id}")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert "estimated_ready_at" in body


async def test_report_200_completed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    anomaly = await AnomalyRepo.create(
        db_session, _anomaly_data(report_status=ReportStatus.completed)
    )
    report = await ReportRepo.create(db_session, _report_data(anomaly.id))
    await db_session.flush()

    resp = await client.get(f"/api/v1/reports/{anomaly.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(report.id)
    assert body["anomaly_id"] == str(anomaly.id)
    assert body["summary"] == "Unusual volume spike detected."
    assert isinstance(body["reasons"], list)
    assert body["confidence"] == pytest.approx(0.82)


async def test_report_200_failed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    anomaly = await AnomalyRepo.create(
        db_session, _anomaly_data(report_status=ReportStatus.failed)
    )
    await db_session.flush()

    resp = await client.get(f"/api/v1/reports/{anomaly.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] == "generation_failed"
