"""
Anomaly detection service — pure functions, zero database calls.

V1: Z-score volume anomaly detection only.  No IQR (deferred to V2).

Severity thresholds:
  zscore > 3.5  → HIGH
  zscore > 2.5  → MEDIUM
  zscore ≤ 2.5  → no anomaly (return None)

Minimum candles required: 20.  If fewer exist, run_detection returns None.
If std == 0 (all volumes identical), there is no meaningful spike; return None.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.repositories.market_repo import RollingStats


@dataclass(frozen=True)
class DetectionResult:
    is_anomaly: bool
    zscore: float | None
    severity: str | None  # "HIGH" | "MEDIUM" | None


_ZSCORE_HIGH: float = 3.5
_ZSCORE_MEDIUM: float = 2.5
_MIN_CANDLES: int = 20


def detect_volume_zscore(current_volume: int, mean: float, std: float) -> float:
    """
    Compute the Z-score of `current_volume` relative to a rolling distribution.

    Callers are responsible for ensuring std > 0 before calling this function.
    """
    return (current_volume - mean) / std


def determine_severity(zscore: float) -> str | None:
    """
    Map a Z-score to a severity label.

    Returns "HIGH", "MEDIUM", or None (no anomaly).
    The boundary value 3.5 is MEDIUM (strictly-greater-than rule for HIGH).
    """
    if zscore > _ZSCORE_HIGH:
        return "HIGH"
    if zscore > _ZSCORE_MEDIUM:
        return "MEDIUM"
    return None


def run_detection(current_volume: int, stats: RollingStats) -> DetectionResult:
    """
    Run the full V1 detection pipeline against rolling stats.

    Returns DetectionResult(is_anomaly=False, zscore=None, severity=None) when:
    - fewer than 20 candles exist (stats.count < MIN_CANDLES)
    - std is 0 (all volumes identical — no meaningful spike)
    - zscore is below the MEDIUM threshold
    """
    if stats.count < _MIN_CANDLES:
        return DetectionResult(is_anomaly=False, zscore=None, severity=None)
    if stats.std == 0.0:
        return DetectionResult(is_anomaly=False, zscore=None, severity=None)

    zscore = detect_volume_zscore(current_volume, stats.mean, stats.std)
    severity = determine_severity(zscore)

    return DetectionResult(
        is_anomaly=severity is not None,
        zscore=zscore,
        severity=severity,
    )
