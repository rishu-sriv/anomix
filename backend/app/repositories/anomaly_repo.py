"""
AnomalyRepo — all SQL for the anomalies table lives here and nowhere else.

Rules:
- No business logic.  Functions store/fetch rows and return ORM objects.
- Callers own the transaction (commit/rollback). This repo only flushes.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import Anomaly, ReportStatus, Severity


class AnomalyRepo:
    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    async def create(session: AsyncSession, anomaly_data: dict) -> Anomaly:
        """Insert a new anomaly row.  Returns the persisted ORM object."""
        anomaly = Anomaly(**anomaly_data)
        session.add(anomaly)
        await session.flush()
        await session.refresh(anomaly)
        return anomaly

    @staticmethod
    async def update_report_status(
        session: AsyncSession, anomaly_id: uuid.UUID, status: ReportStatus
    ) -> None:
        """Update report_status on a single anomaly row."""
        anomaly = await AnomalyRepo.get_by_id(session, anomaly_id)
        if anomaly is not None:
            anomaly.report_status = status
            await session.flush()

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_recent(
        session: AsyncSession,
        ticker: str | None = None,
        hours: int = 24,
        severity: Severity | None = None,
        cursor_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[Anomaly], bool]:
        """
        Return anomalies newest-first, optionally filtered by ticker/severity.
        `cursor_id` is the UUID of the last-seen anomaly (keyset pagination).
        Returns (rows, has_more).
        """
        since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        stmt = select(Anomaly).where(Anomaly.detected_at >= since)

        if ticker is not None:
            stmt = stmt.where(Anomaly.ticker == ticker)
        if severity is not None:
            stmt = stmt.where(Anomaly.severity == severity)

        if cursor_id is not None:
            # Look up detected_at of the cursor anomaly for keyset pagination
            cursor_sub = select(Anomaly.detected_at).where(Anomaly.id == cursor_id)
            cursor_result = await session.execute(cursor_sub)
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time is not None:
                stmt = stmt.where(Anomaly.detected_at < cursor_time)

        stmt = stmt.order_by(Anomaly.detected_at.desc()).limit(limit + 1)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    @staticmethod
    async def get_by_id(
        session: AsyncSession, anomaly_id: uuid.UUID
    ) -> Anomaly | None:
        """Fetch a single anomaly by primary key."""
        stmt = select(Anomaly).where(Anomaly.id == anomaly_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def count_last_24h(session: AsyncSession) -> int:
        """Count anomalies detected in the last 24 hours (all tickers)."""
        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
        stmt = select(func.count()).select_from(Anomaly).where(
            Anomaly.detected_at >= since
        )
        result = await session.execute(stmt)
        return result.scalar_one()
