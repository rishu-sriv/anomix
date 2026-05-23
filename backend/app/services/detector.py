"""
Anomaly detection service — pure functions, zero database calls.

V1: Z-score volume anomaly detection only.
V2: IQR price swing detection + two-signal severity matrix.

Z-score thresholds:
  zscore > 3.5  → HIGH
  zscore > 2.5  → MEDIUM
  zscore ≤ 2.5  → no anomaly (return None)

IQR fence (Tukey standard):
  price < Q1 - 1.5 * IQR  → swing below lower fence
  price > Q3 + 1.5 * IQR  → swing above upper fence

Two-signal severity matrix:
  HIGH z-score + IQR  → HIGH
  HIGH z-score alone  → HIGH
  MEDIUM z-score + IQR → HIGH  (escalated)
  MEDIUM z-score alone → MEDIUM
  IQR alone            → MEDIUM
  Neither              → no anomaly

Minimum candles required: 20.  If fewer exist, detection skips entirely.
If std == 0 (all volumes identical), Z-score path returns None.
If IQR == 0 (all prices identical), IQR path returns False.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.repositories.market_repo import RollingStats


@dataclass(frozen=True)
class DetectionResult:
    is_anomaly: bool
    zscore: float | None
    severity: str | None  # "HIGH" | "MEDIUM" | None
    iqr_flag: bool = False
    price_swing: float | None = None  # close price when iqr_flag is True, else None


@dataclass(frozen=True)
class IQRStats:
    q1: float
    q3: float
    iqr: float
    count: int


_ZSCORE_HIGH: float = 3.5
_ZSCORE_MEDIUM: float = 2.5
_IQR_MULTIPLIER: float = 1.5
_MIN_CANDLES: int = 20


# ── Z-score helpers ───────────────────────────────────────────────────────────


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
    Run the V1 Z-score-only detection pipeline against rolling stats.

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


# ── IQR helpers ───────────────────────────────────────────────────────────────


def _percentile(sorted_values: list[float], pct: float) -> float:
    """
    Compute a percentile using linear interpolation (matches numpy default).

    Args:
        sorted_values: Pre-sorted list of floats (ascending).
        pct: Percentile in range [0, 100].

    Uses the formula: i = pct/100 * (n-1), interpolate between floor and ceil.
    This matches numpy percentile with method='linear' and PostgreSQL percentile_cont.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    i = pct / 100.0 * (n - 1)
    lo = int(math.floor(i))
    hi = int(math.ceil(i))
    frac = i - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def compute_iqr_stats(prices: list[float]) -> IQRStats:
    """
    Compute Q1, Q3, and IQR from a list of close prices.

    Returns IQRStats with count = len(prices).
    Callers must guard on count < MIN_CANDLES before using the result.
    Uses linear interpolation for percentiles — consistent with numpy and
    PostgreSQL percentile_cont.
    """
    count = len(prices)
    if count == 0:
        return IQRStats(q1=0.0, q3=0.0, iqr=0.0, count=0)

    sorted_prices = sorted(prices)
    q1 = _percentile(sorted_prices, 25.0)
    q3 = _percentile(sorted_prices, 75.0)
    iqr = q3 - q1
    return IQRStats(q1=q1, q3=q3, iqr=iqr, count=count)


def detect_price_iqr(current_close: float, iqr_stats: IQRStats) -> bool:
    """
    Return True if current_close is an outlier by the Tukey IQR fence.

    Fence: price < (Q1 - 1.5 * IQR) or price > (Q3 + 1.5 * IQR).
    Returns False if iqr_stats.count < MIN_CANDLES or IQR == 0.
    """
    if iqr_stats.count < _MIN_CANDLES:
        return False
    if iqr_stats.iqr == 0.0:
        return False

    lower_fence = iqr_stats.q1 - _IQR_MULTIPLIER * iqr_stats.iqr
    upper_fence = iqr_stats.q3 + _IQR_MULTIPLIER * iqr_stats.iqr

    return current_close < lower_fence or current_close > upper_fence


# ── Two-signal severity matrix ────────────────────────────────────────────────


def determine_combined_severity(
    zscore_severity: str | None,
    iqr_flag: bool,
) -> str | None:
    """
    Two-signal severity matrix.

    | Z-score severity | IQR flag | Result  |
    |------------------|----------|---------|
    | HIGH             | True     | HIGH    |
    | HIGH             | False    | HIGH    |
    | MEDIUM           | True     | HIGH    |  ← escalated
    | MEDIUM           | False    | MEDIUM  |
    | None             | True     | MEDIUM  |  ← IQR-only
    | None             | False    | None    |
    """
    if zscore_severity == "HIGH":
        return "HIGH"
    if zscore_severity == "MEDIUM" and iqr_flag:
        return "HIGH"
    if zscore_severity == "MEDIUM":
        return "MEDIUM"
    if iqr_flag:
        return "MEDIUM"
    return None


# ── Combined V2 runner ────────────────────────────────────────────────────────


def run_combined_detection(
    current_volume: int,
    current_close: float,
    volume_stats: RollingStats,
    close_prices: list[float],
) -> DetectionResult:
    """
    Full V2 detection pipeline: Z-score on volume + IQR on price.

    Args:
        current_volume: Volume of the latest candle.
        current_close: Close price of the latest candle.
        volume_stats: Rolling stats from last 20 candles (from MarketRepo).
        close_prices: Last 20 close prices (newest first, from MarketRepo).

    Returns DetectionResult with combined severity from the two-signal matrix.
    Both signals require at least 20 candles to fire; with fewer candles neither
    signal activates and is_anomaly is False.
    """
    # ── Z-score on volume ──────────────────────────────────────────────────────
    if volume_stats.count < _MIN_CANDLES or volume_stats.std == 0.0:
        zscore: float | None = None
        zscore_severity: str | None = None
    else:
        zscore = detect_volume_zscore(current_volume, volume_stats.mean, volume_stats.std)
        zscore_severity = determine_severity(zscore)

    # ── IQR on close price ────────────────────────────────────────────────────
    iqr_stats = compute_iqr_stats(close_prices)
    iqr_flag = detect_price_iqr(current_close, iqr_stats)

    # ── Two-signal severity matrix ────────────────────────────────────────────
    severity = determine_combined_severity(zscore_severity, iqr_flag)

    return DetectionResult(
        is_anomaly=severity is not None,
        zscore=zscore,
        severity=severity,
        iqr_flag=iqr_flag,
        price_swing=current_close if iqr_flag else None,
    )
