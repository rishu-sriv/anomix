"""
Unit tests for app/services/detector.py.

All functions are pure — no DB, no fixtures, no async.
Minimum 8 test cases per spec.
"""

import pytest

from app.repositories.market_repo import RollingStats
from app.services.detector import (
    detect_volume_zscore,
    determine_severity,
    run_detection,
)

# ── detect_volume_zscore ──────────────────────────────────────────────────────


def test_zscore_positive_spike() -> None:
    z = detect_volume_zscore(current_volume=3_000_000, mean=1_000_000.0, std=500_000.0)
    assert z == pytest.approx(4.0)


def test_zscore_below_mean() -> None:
    z = detect_volume_zscore(current_volume=500_000, mean=1_000_000.0, std=500_000.0)
    assert z == pytest.approx(-1.0)


# ── determine_severity ────────────────────────────────────────────────────────


def test_determine_severity_high() -> None:
    assert determine_severity(3.6) == "HIGH"


def test_determine_severity_medium() -> None:
    assert determine_severity(2.6) == "MEDIUM"


def test_determine_severity_boundary_35_is_medium() -> None:
    # Boundary: zscore exactly 3.5 is MEDIUM (strictly-greater-than for HIGH)
    assert determine_severity(3.5) == "MEDIUM"


def test_determine_severity_none_below_threshold() -> None:
    assert determine_severity(2.5) is None
    assert determine_severity(1.0) is None
    assert determine_severity(0.0) is None


# ── run_detection ─────────────────────────────────────────────────────────────


def _stats(mean: float, std: float, count: int = 20) -> RollingStats:
    return RollingStats(mean=mean, std=std, count=count)


def test_normal_data_no_anomaly() -> None:
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=1_050_000, stats=stats)
    assert result.is_anomaly is False
    assert result.severity is None
    assert result.zscore == pytest.approx(0.5)


def test_clear_spike_high() -> None:
    stats = _stats(mean=1_000_000.0, std=200_000.0)
    result = run_detection(current_volume=2_000_000, stats=stats)
    assert result.is_anomaly is True
    assert result.severity == "HIGH"
    assert result.zscore == pytest.approx(5.0)


def test_borderline_just_below_25_no_anomaly() -> None:
    # zscore = (1_249_999 - 1_000_000) / 100_000 = 2.4999..
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=1_249_999, stats=stats)
    assert result.is_anomaly is False
    assert result.severity is None


def test_borderline_just_above_25_medium() -> None:
    # zscore ≈ 2.51
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=1_251_000, stats=stats)
    assert result.is_anomaly is True
    assert result.severity == "MEDIUM"


def test_boundary_35_is_medium_not_high() -> None:
    # zscore exactly 3.5 → MEDIUM (strictly-greater-than for HIGH)
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=1_350_000, stats=stats)
    assert result.severity == "MEDIUM"
    assert result.zscore == pytest.approx(3.5)


def test_just_above_35_is_high() -> None:
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=1_350_001, stats=stats)
    assert result.severity == "HIGH"


def test_std_zero_no_anomaly_no_divide_by_zero() -> None:
    # All volumes identical — std = 0.  Should return no anomaly, not raise ZeroDivisionError.
    stats = _stats(mean=1_000_000.0, std=0.0)
    result = run_detection(current_volume=1_000_000, stats=stats)
    assert result.is_anomaly is False
    assert result.zscore is None


def test_fewer_than_20_candles_skips_detection() -> None:
    stats = _stats(mean=1_000_000.0, std=200_000.0, count=19)
    result = run_detection(current_volume=5_000_000, stats=stats)
    assert result.is_anomaly is False
    assert result.zscore is None


def test_extreme_outlier_high() -> None:
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    result = run_detection(current_volume=2_500_000, stats=stats)
    assert result.is_anomaly is True
    assert result.severity == "HIGH"
    assert result.zscore == pytest.approx(15.0)
