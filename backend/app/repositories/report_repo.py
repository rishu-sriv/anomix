"""
ReportRepo — all SQL for the reports table lives here and nowhere else.

Rules:
- No business logic.  Functions store/fetch rows and return ORM objects.
- Callers own the transaction (commit/rollback). This repo only flushes.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


class ReportRepo:
    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    async def create(session: AsyncSession, report_data: dict) -> Report:
        """Insert a new report row.  Returns the persisted ORM object."""
        report = Report(**report_data)
        session.add(report)
        await session.flush()
        await session.refresh(report)
        return report

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_by_anomaly_id(
        session: AsyncSession, anomaly_id: uuid.UUID
    ) -> Report | None:
        """Fetch the report linked to `anomaly_id`, or None if not yet generated."""
        stmt = select(Report).where(Report.anomaly_id == anomaly_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
