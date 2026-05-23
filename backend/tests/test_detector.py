"""
Unit tests for app/services/detector.py.

All functions are pure — no DB, no fixtures, no async.
V1 tests: Z-score detection (10 cases)
V2 tests: IQR detection (6 cases) + two-signal matrix (6 cases) + combined runner (5 cases)
"""

import pytest

from app.repositories.market_repo import RollingStats
from app.services.detector import (
    compute_iqr_stats,
    detect_price_iqr,
    detect_volume_zscore,
    determine_combined_severity,
    determine_severity,
    run_combined_detection,
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


# ── run_detection (V1 Z-score only) ──────────────────────────────────────────


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


# ── compute_iqr_stats ─────────────────────────────────────────────────────────


def _close_prices(base: float = 100.0, n: int = 20) -> list[float]:
    """Generate n close prices tightly clustered around base."""
    return [base + (i % 5) * 0.1 for i in range(n)]


def test_iqr_stats_basic() -> None:
    prices = list(range(1, 21, 1))  # 1..20 as floats
    prices_f = [float(p) for p in prices]
    stats = compute_iqr_stats(prices_f)
    assert stats.count == 20
    assert stats.q1 == pytest.approx(5.75)   # numpy default: linear interpolation
    assert stats.q3 == pytest.approx(15.25)
    assert stats.iqr == pytest.approx(9.5)


def test_iqr_stats_single_value() -> None:
    stats = compute_iqr_stats([100.0])
    assert stats.count == 1
    assert stats.q1 == pytest.approx(100.0)
    assert stats.q3 == pytest.approx(100.0)
    assert stats.iqr == pytest.approx(0.0)


def test_iqr_stats_empty() -> None:
    stats = compute_iqr_stats([])
    assert stats.count == 0
    assert stats.iqr == pytest.approx(0.0)


# ── detect_price_iqr ──────────────────────────────────────────────────────────


def _iqr_stats_from_prices(prices: list[float]):
    return compute_iqr_stats(prices)


def test_iqr_normal_price_no_flag() -> None:
    prices = _close_prices(base=100.0, n=20)
    iqr_stats = _iqr_stats_from_prices(prices)
    # Price within the cluster — should not flag
    result = detect_price_iqr(current_close=100.2, iqr_stats=iqr_stats)
    assert result is False


def test_iqr_extreme_high_flags() -> None:
    # Create a tight cluster, then present a far outlier above Q3 + 1.5*IQR
    prices = [100.0] * 15 + [101.0] * 5  # tight range
    iqr_stats = _iqr_stats_from_prices(prices)
    # The IQR here is very small; 150.0 is far above the upper fence
    result = detect_price_iqr(current_close=150.0, iqr_stats=iqr_stats)
    assert result is True


def test_iqr_extreme_low_flags() -> None:
    prices = [100.0] * 15 + [101.0] * 5
    iqr_stats = _iqr_stats_from_prices(prices)
    result = detect_price_iqr(current_close=50.0, iqr_stats=iqr_stats)
    assert result is True


def test_iqr_zero_iqr_no_flag() -> None:
    # All prices identical → IQR = 0 → any price returns False (no divide by zero)
    prices = [100.0] * 20
    iqr_stats = _iqr_stats_from_prices(prices)
    assert iqr_stats.iqr == pytest.approx(0.0)
    result = detect_price_iqr(current_close=100.0, iqr_stats=iqr_stats)
    assert result is False
    result_outlier = detect_price_iqr(current_close=999.0, iqr_stats=iqr_stats)
    assert result_outlier is False  # still False because IQR == 0


def test_iqr_fewer_than_20_no_flag() -> None:
    prices = [100.0] * 19  # one fewer than minimum
    from app.services.detector import IQRStats
    iqr_stats = IQRStats(q1=99.0, q3=101.0, iqr=2.0, count=19)
    result = detect_price_iqr(current_close=999.0, iqr_stats=iqr_stats)
    assert result is False


def test_iqr_at_fence_boundary_no_flag() -> None:
    # Exactly at the fence = not flagged (strict greater-than)
    prices = [float(p) for p in range(1, 21)]
    iqr_stats = _iqr_stats_from_prices(prices)
    upper_fence = iqr_stats.q3 + 1.5 * iqr_stats.iqr
    result = detect_price_iqr(current_close=upper_fence, iqr_stats=iqr_stats)
    assert result is False


# ── determine_combined_severity ───────────────────────────────────────────────


def test_combined_high_zscore_no_iqr() -> None:
    assert determine_combined_severity("HIGH", False) == "HIGH"


def test_combined_high_zscore_with_iqr() -> None:
    assert determine_combined_severity("HIGH", True) == "HIGH"


def test_combined_medium_zscore_no_iqr() -> None:
    assert determine_combined_severity("MEDIUM", False) == "MEDIUM"


def test_combined_medium_zscore_with_iqr_escalates() -> None:
    # MEDIUM + IQR → HIGH (two-signal escalation)
    assert determine_combined_severity("MEDIUM", True) == "HIGH"


def test_combined_iqr_only() -> None:
    # No Z-score but IQR fires → MEDIUM
    assert determine_combined_severity(None, True) == "MEDIUM"


def test_combined_neither_signal() -> None:
    assert determine_combined_severity(None, False) is None


# ── run_combined_detection ────────────────────────────────────────────────────


def _make_closes(tight: bool = True) -> list[float]:
    if tight:
        return [100.0 + (i % 3) * 0.05 for i in range(20)]  # very tight range
    return [float(p) for p in range(81, 101)]  # spread range


def test_combined_both_signals_high() -> None:
    # High Z-score + IQR outlier → HIGH (escalated)
    stats = _stats(mean=1_000_000.0, std=200_000.0)
    closes = _make_closes(tight=True)
    # Volume spike is HIGH, price is far outside the tight IQR fence
    result = run_combined_detection(
        current_volume=2_000_000,
        current_close=999.0,
        volume_stats=stats,
        close_prices=closes,
    )
    assert result.is_anomaly is True
    assert result.severity == "HIGH"
    assert result.iqr_flag is True
    assert result.zscore is not None


def test_combined_zscore_only_medium() -> None:
    # MEDIUM Z-score + no IQR → MEDIUM
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    closes = _make_closes(tight=True)
    result = run_combined_detection(
        current_volume=1_260_000,  # just above 2.5 threshold
        current_close=100.0,       # inside fence
        volume_stats=stats,
        close_prices=closes,
    )
    assert result.is_anomaly is True
    assert result.severity == "MEDIUM"
    assert result.iqr_flag is False


def test_combined_iqr_only_medium() -> None:
    # No Z-score (normal volume) but IQR outlier → MEDIUM
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    closes = _make_closes(tight=True)
    result = run_combined_detection(
        current_volume=1_050_000,  # z-score = 0.5, below threshold
        current_close=999.0,       # far outside fence
        volume_stats=stats,
        close_prices=closes,
    )
    assert result.is_anomaly is True
    assert result.severity == "MEDIUM"
    assert result.iqr_flag is True
    assert result.zscore == pytest.approx(0.5)


def test_combined_no_signal() -> None:
    stats = _stats(mean=1_000_000.0, std=100_000.0)
    closes = _make_closes(tight=True)
    result = run_combined_detection(
        current_volume=1_050_000,
        current_close=100.0,
        volume_stats=stats,
        close_prices=closes,
    )
    assert result.is_anomaly is False
    assert result.severity is None
    assert result.iqr_flag is False


def test_combined_fewer_than_20_candles_no_anomaly() -> None:
    stats = _stats(mean=1_000_000.0, std=200_000.0, count=19)
    closes = [100.0] * 19  # fewer than 20
    result = run_combined_detection(
        current_volume=5_000_000,
        current_close=999.0,
        volume_stats=stats,
        close_prices=closes,
    )
    assert result.is_anomaly is False
    assert result.zscore is None
    assert result.iqr_flag is False
