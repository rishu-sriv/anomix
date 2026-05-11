"""
Ingestion task — fetches TSLA OHLCV candles from yfinance every 60 seconds.

Design decisions:
- asyncio.run() creates a new event loop per task invocation. Safe with Celery's
  default prefork pool (each task runs in a subprocess). Do NOT use with eventlet
  or gevent pool — those require a different async integration.
- ON CONFLICT DO NOTHING in MarketRepo.upsert_candles makes this fully idempotent.
- Chains detect_anomalies only when new rows were actually inserted — avoids
  wasting detection cycles when the market is closed or yfinance returns stale data.

Retry policy: up to 3 retries with exponential back-off (30s, 60s, 120s).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timezone

import pandas as pd
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.repositories.market_repo import MarketRepo
from workers.celery_app import app

logger = logging.getLogger(__name__)


# ── Async core ────────────────────────────────────────────────────────────────


async def _ingest(ticker: str) -> int:
    """
    Fetch 1-minute candles from yfinance and upsert into market_data.

    Returns the number of rows newly inserted (0 if all were duplicates or
    no new candles since last ingestion).
    """
    engine = create_async_engine(settings.async_database_url, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            last_time = await MarketRepo.get_latest_time(session, ticker)

            # yfinance returns a MultiIndex DataFrame when passed a list of tickers.
            # Column order: (field, ticker) — e.g. ('Open', 'TSLA').
            # We pass a list so we always get MultiIndex, regardless of ticker count.
            df: pd.DataFrame = yf.download(
                [ticker],
                interval="1m",
                period="1d",
                progress=False,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning("yfinance returned empty DataFrame for %s", ticker)
                return 0

            # Flatten MultiIndex: get_level_values(0) gives the field names
            # (Open, High, Low, Close, Volume), dropping the ticker level.
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df.columns = [str(c).lower() for c in df.columns]
            df.index.name = "time"
            df = df.reset_index()

            # Ensure all timestamps are UTC-aware
            if df["time"].dt.tz is None:
                df["time"] = df["time"].dt.tz_localize("UTC")
            else:
                df["time"] = df["time"].dt.tz_convert("UTC")

            # Drop rows with NaN or zero volume (incomplete candles)
            df = df.dropna(subset=["volume"])
            df = df[df["volume"] > 0]

            # Skip candles we already have
            if last_time is not None:
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                df = df[df["time"] > last_time]

            if df.empty:
                logger.debug("No new candles for %s", ticker)
                return 0

            candles = [
                {
                    "time": row.time.to_pydatetime(),
                    "ticker": ticker,
                    "open": round(float(row.open), 4),
                    "high": round(float(row.high), 4),
                    "low": round(float(row.low), 4),
                    "close": round(float(row.close), 4),
                    "volume": int(row.volume),
                }
                for row in df.itertuples()
            ]

            inserted = await MarketRepo.upsert_candles(session, candles)
            await session.commit()
            logger.info("Ingested %d new candles for %s", inserted, ticker)
            return inserted
    finally:
        await engine.dispose()


# ── Celery task ───────────────────────────────────────────────────────────────


@app.task(
    name="workers.ingestion_task.ingest_market_data",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def ingest_market_data(self, ticker: str = "TSLA") -> None:  # type: ignore[misc]
    """
    Celery entry point: ingest candles then chain detection if new data arrived.

    Import detect_anomalies here (not at module level) to avoid circular
    imports during Celery's task discovery phase.
    """
    from workers.detection_task import detect_anomalies  # late import

    try:
        inserted = asyncio.run(_ingest(ticker))
        if inserted > 0:
            detect_anomalies.delay(ticker)
    except Exception as exc:
        logger.exception("Ingestion failed for %s: %s", ticker, exc)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
