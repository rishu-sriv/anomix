"""
GET /api/v1/stocks/{ticker}/candles

Returns paginated OHLCV candles for a ticker.
Query params: interval=1m|5m|15m (V1: only 1m stored), hours=1-168, cursor?

`cursor` is an ISO-8601 datetime string (the time of the oldest candle in the
previous page).  `next_cursor` in the response is the same format.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.market_repo import MarketRepo
from app.schemas.market import CandleListResponse, CandleSchema

router = APIRouter()


@router.get("/stocks/{ticker}/candles", response_model=CandleListResponse)
async def get_candles(
    ticker: str,
    interval: str = Query(default="1m", pattern="^(1m|5m|15m)$"),
    hours: int = Query(default=1, ge=1, le=168),
    cursor: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> CandleListResponse:
    rows, has_more = await MarketRepo.get_candles(
        session, ticker=ticker.upper(), hours=hours, cursor=cursor, limit=100
    )
    next_cursor = rows[-1].time.isoformat() if has_more and rows else None
    return CandleListResponse(
        data=[CandleSchema.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
        ticker=ticker.upper(),
    )
