from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class CandleSchema(BaseModel):
    """One OHLCV candle.  `time` is serialised as a Unix integer timestamp."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    ticker: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @field_serializer("time")
    def serialize_time(self, v: datetime) -> int:
        return int(v.timestamp())


class CandleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: list[CandleSchema]
    next_cursor: str | None
    has_more: bool
    ticker: str
