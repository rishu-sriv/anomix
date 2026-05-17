"""
Report task — generates (or mocks) an AI report for a detected anomaly.

Called by: detection_task.detect_anomalies (chained after anomaly creation)

Flow:
  1. Fetch the Anomaly row from DB
  2. Check if a Report already exists — if yes, stop (idempotency)
  3. Fetch rolling stats + recent candles (passed to reporter for context)
  4. Call generate_report() — real Claude API call (or mock when USE_MOCK_REPORTS=true)
  5. Write Report row, update anomaly.report_status = completed
  6. Publish report_ready event to Redis (best-effort — failure does not fail the task)
  7. On any exception in steps 4-5: set anomaly.report_status = failed

Idempotency:
  ReportRepo.get_by_anomaly_id() check ensures we never write two reports for
  the same anomaly, even on task retry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.anomaly import ReportStatus
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo
from app.services.reporter import generate_report as _generate_report
from workers.celery_app import app

logger = logging.getLogger(__name__)


# ── Async core ────────────────────────────────────────────────────────────────


async def _generate(anomaly_id_str: str) -> None:
    """
    Generate and persist a report for the given anomaly.

    Sets report_status=failed on the anomaly if report generation raises.
    Publishes a report_ready event to Redis after a successful write.
    """
    engine = create_async_engine(settings.async_database_url, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            anomaly_id = uuid.UUID(anomaly_id_str)

            anomaly = await AnomalyRepo.get_by_id(session, anomaly_id)
            if anomaly is None:
                logger.warning("Report task: anomaly %s not found — skipping", anomaly_id)
                return

            # Idempotency guard — never write two reports for the same anomaly
            existing = await ReportRepo.get_by_anomaly_id(session, anomaly_id)
            if existing is not None:
                logger.info("Report already exists for anomaly %s — skipping", anomaly_id)
                return

            # Fetch context for the reporter
            stats = await MarketRepo.get_rolling_stats(session, anomaly.ticker)
            candles, _ = await MarketRepo.get_candles(session, anomaly.ticker, hours=1)

            try:
                report_schema = _generate_report(anomaly, candles, stats)

                await ReportRepo.create(
                    session,
                    {
                        "id": report_schema.id,
                        "anomaly_id": report_schema.anomaly_id,
                        "summary": report_schema.summary,
                        "reasons": report_schema.reasons,
                        "risk_level": report_schema.risk_level,
                        "confidence": report_schema.confidence,
                        "tokens_used": report_schema.tokens_used,
                        "latency_ms": report_schema.latency_ms,
                        "created_at": report_schema.created_at,
                    },
                )
                await AnomalyRepo.update_report_status(
                    session, anomaly_id, ReportStatus.completed
                )
                await session.commit()

                logger.info(
                    "Report generated for anomaly %s (latency=%dms tokens=%d)",
                    anomaly_id,
                    report_schema.latency_ms,
                    report_schema.tokens_used,
                )

                # ── Publish report_ready event (best-effort) ──────────────────
                # Failure here is non-fatal — the report is already persisted.
                # Downstream consumers (e.g. WebSocket broadcast in V2) listen
                # to this channel to push notifications to connected clients.
                await _publish_report_ready(
                    anomaly_id_str,
                    anomaly.ticker,
                    anomaly.severity.value,
                )

            except Exception as report_exc:
                # Mark failed so the frontend shows "Report unavailable"
                await AnomalyRepo.update_report_status(
                    session, anomaly_id, ReportStatus.failed
                )
                await session.commit()
                logger.exception(
                    "Report generation failed for anomaly %s: %s",
                    anomaly_id,
                    report_exc,
                )
                raise
    finally:
        await engine.dispose()


async def _publish_report_ready(
    anomaly_id_str: str,
    ticker: str,
    severity: str,
) -> None:
    """
    Publish a report_ready event to the Redis finpulse:reports channel.

    Creates a short-lived Redis connection for the publish and closes it immediately.
    Any exception is logged but not re-raised — Redis availability must not affect
    report persistence.
    """
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        payload = json.dumps(
            {
                "anomaly_id": anomaly_id_str,
                "status": "ready",
                "ticker": ticker,
                "severity": severity,
            }
        )
        await redis_client.publish("finpulse:reports", payload)
        await redis_client.aclose()
        logger.debug("Published report_ready for anomaly %s", anomaly_id_str)
    except Exception as exc:
        logger.warning(
            "Failed to publish report_ready for anomaly %s: %s — report is persisted, continuing",
            anomaly_id_str,
            exc,
        )


# ── Celery task ───────────────────────────────────────────────────────────────


@app.task(
    name="workers.report_task.generate_report",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def generate_report(self, anomaly_id: str) -> None:  # type: ignore[misc]
    """Celery entry point: generate and persist a report for the given anomaly."""
    try:
        asyncio.run(_generate(anomaly_id))
    except Exception as exc:
        logger.exception("Report task failed for anomaly %s: %s", anomaly_id, exc)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
