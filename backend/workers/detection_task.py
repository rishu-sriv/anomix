"""
Detection task — runs combined anomaly detection (Z-score + IQR) on the latest candle.

Called by: ingestion_task.ingest_market_data (chained, only when new candles inserted)

Flow:
  1. Fetch rolling volume stats (mean, std, count) from last 20 candles
  2. Fetch last 20 close prices for IQR computation
  3. Fetch the most recent candle
  4. Run run_combined_detection(volume, close, stats, closes) — pure, no DB calls
  5. If anomaly: write Anomaly row with report_status=pending
     - type=volume_spike if Z-score fired (with or without IQR)
     - type=price_swing if IQR-only (no Z-score signal)
  6. Chain generate_report(anomaly_id)
  7. If no anomaly or < 20 candles: log and stop

Idempotency: duplicate detection on the same candle is prevented by the unique
constraint on (candle_time, ticker) in anomalies. IntegrityError is caught and
logged — no retry on duplicate.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.anomaly import AnomalyType, ReportStatus, Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.services.detector import run_combined_detection
from workers.celery_app import app

logger = logging.getLogger(__name__)


# ── Async core ────────────────────────────────────────────────────────────────


async def _detect(ticker: str) -> str | None:
    """
    Run combined detection and write an Anomaly row if triggered.
    Returns the anomaly UUID string, or None if no anomaly was detected.
    """
    engine = create_async_engine(settings.async_database_url, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Fetch rolling volume stats and latest close prices (last 20 candles)
            stats = await MarketRepo.get_rolling_stats(session, ticker)
            close_prices = await MarketRepo.get_recent_closes(session, ticker, limit=20)

            # Fetch just the most recent candle
            candles, _ = await MarketRepo.get_candles(session, ticker, hours=24, limit=1)
            if not candles:
                logger.debug("No candles found for %s — skipping detection", ticker)
                return None

            latest = candles[0]
            result = run_combined_detection(
                current_volume=int(latest.volume),
                current_close=float(latest.close),
                volume_stats=stats,
                close_prices=close_prices,
            )

            if not result.is_anomaly:
                logger.debug(
                    "No anomaly for %s (zscore=%s, iqr_flag=%s, count=%d)",
                    ticker,
                    f"{result.zscore:.2f}" if result.zscore is not None else "N/A",
                    result.iqr_flag,
                    stats.count,
                )
                return None

            # Determine anomaly type:
            # If Z-score fired → volume_spike (even if IQR also fired).
            # If IQR-only (no Z-score) → price_swing.
            anomaly_type = (
                AnomalyType.price_swing
                if result.iqr_flag and result.zscore is None
                else AnomalyType.volume_spike
            )

            try:
                anomaly = await AnomalyRepo.create(
                    session,
                    {
                        "id": uuid.uuid4(),
                        "detected_at": datetime.now(tz=timezone.utc),
                        "candle_time": latest.time,
                        "ticker": ticker,
                        "type": anomaly_type,
                        "severity": Severity[result.severity],  # type: ignore[index]
                        "zscore": result.zscore,
                        "iqr_flag": result.iqr_flag,
                        "report_status": ReportStatus.pending,
                    },
                )
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.info(
                    "Duplicate anomaly skipped for %s candle_time=%s (unique constraint)",
                    ticker,
                    latest.time,
                )
                return None

            logger.info(
                "Anomaly detected for %s: type=%s severity=%s zscore=%s iqr=%s id=%s",
                ticker,
                anomaly_type.value,
                result.severity,
                f"{result.zscore:.2f}" if result.zscore is not None else "N/A",
                result.iqr_flag,
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
