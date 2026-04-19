import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    anomaly_id: uuid.UUID
    summary: str
    reasons: list[str]
    risk_level: str
    confidence: float
    tokens_used: int
    latency_ms: int
    created_at: datetime


class ReportPendingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "pending"
    estimated_ready_at: datetime


class ReportFailedSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "failed"
    error: str = "generation_failed"
