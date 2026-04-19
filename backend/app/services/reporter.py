"""
Report generation service — pure functions, zero database calls.

V1: USE_MOCK_REPORTS=true.  generate_report() returns a hardcoded mock immediately.
    No Claude API call is made in V1.

V2 will replace the mock branch with a real Anthropic SDK call + Langfuse tracing.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.models.anomaly import Anomaly
from app.repositories.market_repo import RollingStats
from app.schemas.report import ReportSchema

# ── Mock report content (V1) ──────────────────────────────────────────────────

_MOCK_SUMMARY = (
    "An unusual volume spike was detected for this ticker. "
    "The trading volume significantly exceeded the rolling 20-candle average, "
    "which may indicate institutional activity, a news catalyst, or a technical breakout."
)

_MOCK_REASONS = [
    "Volume exceeded the 20-candle rolling mean by more than 2.5 standard deviations.",
    "No corresponding price breakout was detected in V1 (IQR check deferred to V2).",
    "Spike is consistent with short-term liquidity events observed in equity markets.",
]

_MOCK_RISK_LEVEL = "Medium"
_MOCK_CONFIDENCE = 0.82


def generate_report(
    anomaly: Anomaly,
    candles: list,  # list[MarketData] — typed loosely to avoid circular import
    stats: RollingStats,
) -> ReportSchema:
    """
    Generate a report for the given anomaly.

    V1: USE_MOCK_REPORTS=true → returns a hardcoded mock immediately.
    The `candles` and `stats` arguments are accepted for API compatibility with V2
    but are not used in the mock path.
    """
    start = time.monotonic()

    if settings.use_mock_reports:
        latency_ms = int((time.monotonic() - start) * 1000)
        return ReportSchema(
            id=uuid.uuid4(),
            anomaly_id=anomaly.id,
            summary=_MOCK_SUMMARY,
            reasons=_MOCK_REASONS,
            risk_level=_MOCK_RISK_LEVEL,
            confidence=_MOCK_CONFIDENCE,
            tokens_used=0,
            latency_ms=latency_ms,
            created_at=datetime.now(tz=timezone.utc),
        )

    # V2 placeholder — real Claude API call goes here.
    raise NotImplementedError("Real report generation is a V2 feature.")
