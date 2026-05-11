"""
Detection task — runs Z-score anomaly detection on the latest TSLA candle.

Called by: ingestion_task.ingest_market_data (chained, only when new candles inserted)

Flow:
  1. Fetch rolling stats (mean, std, count) from last 20 candles in market_data
  2. Fetch the most recent candle
  3. Run run_detection(volume, stats) — pure function, no DB calls
  4. If anomaly: write Anomaly row with report_status=pending
  5. Chain generate_report(anomaly_id)
  6. If no anomaly or < 20 candles: log and stop

Idempotency: on retry, detection re-runs on the same latest candle. This may
create a duplicate anomaly row for the same candle. Acceptable in V1 — a
unique constraint on (candle_time, ticker) would prevent this in V2.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.anomaly import AnomalyType, ReportStatus, Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.services.detector import run_detection
from workers.celery_app import app

logger = logging.getLogger(__name__)


# ── Async core ────────────────────────────────────────────────────────────────


async def _detect(ticker: str) -> str | None:
    """
    Run detection and write an Anomaly row if triggered.
    Returns the anomaly UUID string, or None if no anomaly was detected.
    """
    engine = create_async_engine(settings.async_database_url, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Rolling stats from the last 20 candles (as per V1 spec)
            stats = await MarketRepo.get_rolling_stats(session, ticker)

            # Fetch just the most recent candle
            candles, _ = await MarketRepo.get_candles(session, ticker, hours=24, limit=1)
            if not candles:
                logger.debug("No candles found for %s — skipping detection", ticker)
                return None

            latest = candles[0]
            result = run_detection(int(latest.volume), stats)

            if not result.is_anomaly:
                logger.debug(
                    "No anomaly for %s (zscore=%.2f, count=%d)",
                    ticker,
                    result.zscore or 0.0,
                    stats.count,
                )
                return None

            # Severity is guaranteed non-None when is_anomaly is True
            anomaly = await AnomalyRepo.create(
                session,
                {
                    "id": uuid.uuid4(),
                    "detected_at": datetime.now(tz=timezone.utc),
                    "candle_time": latest.time,
                    "ticker": ticker,
                    "type": AnomalyType.volume_spike,
                    "severity": Severity[result.severity],  # type: ignore[index]
                    "zscore": result.zscore,
                    "iqr_flag": False,
                    "report_status": ReportStatus.pending,
                },
            )
            await session.commit()

            logger.info(
                "Anomaly detected for %s: severity=%s zscore=%.2f id=%s",
                ticker,
                result.severity,
                result.zscore or 0.0,
                anomaly.id,
            )
            return str(anomaly.id)
    finally:
        await engine.dispose()


# ── Celery task ───────────────────────────────────────────────────────────────


@app.task(
    name="workers.detection_task.detect_anomalies",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def detect_anomalies(self, ticker: str = "TSLA") -> None:  # type: ignore[misc]
    """
    Celery entry point: detect anomalies, chain report generation if found.
    """
    from workers.report_task import generate_report  # late import

    try:
        anomaly_id = asyncio.run(_detect(ticker))
        if anomaly_id is not None:
            generate_report.delay(anomaly_id)
    except Exception as exc:
        logger.exception("Detection failed for %s: %s", ticker, exc)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
