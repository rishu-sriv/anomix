"""
GET /api/v1/anomalies

Returns a paginated list of anomalies, newest first.
Query params: ticker?, severity?, type?, hours=24, cursor?
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.anomaly import Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.schemas.anomaly import AnomalyListResponse, AnomalySchema

router = APIRouter()


@router.get("/anomalies", response_model=AnomalyListResponse)
async def list_anomalies(
    ticker: str | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    cursor: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    rows, has_more = await AnomalyRepo.get_recent(
        session,
        ticker=ticker,
        hours=hours,
        severity=severity,
        cursor_id=cursor,
        limit=50,
    )
    next_cursor = str(rows[-1].id) if has_more and rows else None
    return AnomalyListResponse(
        data=[AnomalySchema.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
