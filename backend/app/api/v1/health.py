"""
GET /api/v1/health

Checks DB connectivity, Redis connectivity, last ingestion time, and
anomaly count for the last 24 hours.  Returns "healthy" or "degraded".
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    last_ingestion: datetime | None
    anomalies_24h: int


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    redis_status = "ok"
    last_ingestion: datetime | None = None
    anomalies_24h = 0

    try:
        await session.execute(text("SELECT 1"))
        last_ingestion = await MarketRepo.get_latest_time(session, "TSLA")
        anomalies_24h = await AnomalyRepo.count_last_24h(session)
    except Exception:
        db_status = "error"

    try:
        redis = await get_redis()
        await redis.ping()
    except Exception:
        redis_status = "error"

    overall = "healthy" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        db=db_status,
        redis=redis_status,
        last_ingestion=last_ingestion,
        anomalies_24h=anomalies_24h,
    )
