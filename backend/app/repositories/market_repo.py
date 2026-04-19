"""
MarketRepo — all SQL for the market_data table lives here and nowhere else.

Rules:
- No business logic. These functions fetch/store rows and return ORM objects or scalars.
- Callers own the transaction (commit/rollback). This repo only flushes.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import MarketData


class RollingStats:
    """Rolling statistics computed from the last 20 raw candles."""

    __slots__ = ("mean", "std", "count")

    def __init__(self, mean: float, std: float, count: int) -> None:
        self.mean = mean
        self.std = std
        self.count = count


class MarketRepo:
    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    async def upsert_candles(session: AsyncSession, candles: list[dict]) -> int:
        """
        Bulk-upsert OHLCV candles.  ON CONFLICT (time, ticker) DO NOTHING.
        Returns the number of rows actually inserted (conflicts excluded).
        """
        if not candles:
            return 0
        stmt = insert(MarketData).values(candles).on_conflict_do_nothing(
            index_elements=["time", "ticker"]
        )
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount  # type: ignore[return-value]

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_candles(
        session: AsyncSession,
        ticker: str,
        hours: int = 1,
        cursor: datetime | None = None,
        limit: int = 100,
    ) -> tuple[list[MarketData], bool]:
        """
        Return candles for `ticker` over the last `hours`, newest first.
        `cursor` is the exclusive upper bound on `time` for keyset pagination.
        Returns (rows, has_more).
        """
        since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        stmt = select(MarketData).where(
            MarketData.ticker == ticker,
            MarketData.time >= since,
        )
        if cursor is not None:
            stmt = stmt.where(MarketData.time < cursor)
        stmt = stmt.order_by(MarketData.time.desc()).limit(limit + 1)

        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    @staticmethod
    async def get_rolling_stats(
        session: AsyncSession, ticker: str
    ) -> RollingStats:
        """
        Compute rolling mean and stddev of volume from the last 20 raw candles.
        V1 uses raw rows — no continuous aggregate (that is V2).
        Returns RollingStats with count=0 if there is no data.
        """
        # Subquery: last 20 candles by time DESC
        sub = (
            select(MarketData.volume)
            .where(MarketData.ticker == ticker)
            .order_by(MarketData.time.desc())
            .limit(20)
            .subquery()
        )
        stmt = select(
            func.avg(sub.c.volume).label("mean_volume"),
            func.stddev_pop(sub.c.volume).label("std_volume"),
            func.count().label("candle_count"),
        )
        row = (await session.execute(stmt)).one()

        count = int(row.candle_count or 0)
        mean = float(row.mean_volume or 0.0)
        std = float(row.std_volume or 0.0)
        return RollingStats(mean=mean, std=std, count=count)

    @staticmethod
    async def get_latest_time(
        session: AsyncSession, ticker: str
    ) -> datetime | None:
        """Return the timestamp of the most recent candle for `ticker`."""
        stmt = (
            select(MarketData.time)
            .where(MarketData.ticker == ticker)
            .order_by(MarketData.time.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
