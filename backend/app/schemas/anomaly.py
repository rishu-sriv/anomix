import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.anomaly import AnomalyType, ReportStatus, Severity


class AnomalySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    detected_at: datetime
    candle_time: datetime
    ticker: str
    type: AnomalyType
    severity: Severity
    zscore: float | None
    iqr_flag: bool
    report_status: ReportStatus


class AnomalyListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: list[AnomalySchema]
    next_cursor: str | None  # UUID string of the last item, or null
    has_more: bool


class AnomalyEventSchema(BaseModel):
    """Lightweight payload emitted when an anomaly is first detected (V2 WebSocket)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    severity: Severity
    type: AnomalyType
    detected_at: datetime
