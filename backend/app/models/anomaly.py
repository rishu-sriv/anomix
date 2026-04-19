import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnomalyType(str, enum.Enum):
    volume_spike = "volume_spike"
    price_swing = "price_swing"   # V2 — included now so the schema needs no migration later


class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReportStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class Anomaly(Base):
    """
    One row per detected anomaly.  Written by the detection Celery worker.
    report_status tracks whether a report has been generated for this anomaly.
    iqr_flag is always False in V1 (IQR detection deferred to V2).
    """

    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    type: Mapped[AnomalyType] = mapped_column(
        SAEnum(AnomalyType, name="anomalytype", create_type=True), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity", create_type=True), nullable=False
    )
    zscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iqr_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    report_status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="reportstatus", create_type=True),
        default=ReportStatus.pending,
        nullable=False,
    )
