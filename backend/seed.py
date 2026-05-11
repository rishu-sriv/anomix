"""
Seed script — populates the DB with realistic mock data so the dashboard
works immediately without waiting for live market data.

Generates:
  - 40 TSLA 1-minute candles (last 40 minutes, realistic prices)
  - 3 volume-spike anomalies embedded in the candle sequence
  - 3 completed mock reports (one per anomaly)

Run inside the backend container:
  docker exec finpulse_backend python seed.py
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# ── Config ────────────────────────────────────────────────────────────────────

TICKER = "TSLA"
N_CANDLES = 40          # must be >= 20 for detection to fire
BASE_PRICE = 175.00     # realistic TSLA price
BASE_VOLUME = 250_000   # normal 1-min volume
SPIKE_MULTIPLIER = 5.0  # makes zscore well above 2.5

# Candle indices (0-based) that will be volume spikes → anomalies
SPIKE_INDICES = {25, 32, 38}

MOCK_REPORTS = [
    {
        "summary": (
            "TSLA experienced a significant volume spike driven by unusual options "
            "activity ahead of an expected product announcement. The elevated volume "
            "relative to the 20-candle rolling average suggests institutional accumulation."
        ),
        "reasons": [
            "Volume 5.2x above the 20-candle rolling mean",
            "Spike coincided with large call option sweep at $180 strike",
            "Price held firm during the spike — no distribution pattern observed",
            "Similar pattern preceded the Q3 2023 earnings gap-up",
        ],
        "risk_level": "High",
        "confidence": 0.91,
    },
    {
        "summary": (
            "Elevated volume detected on TSLA during a period of broader market "
            "volatility. The spike may reflect index rebalancing flows or a reaction "
            "to macro news rather than company-specific catalysts."
        ),
        "reasons": [
            "Volume 4.8x above rolling mean — statistically significant (z=3.7)",
            "Broad market sell-off coincided with spike window",
            "No company-specific news identified in the 15-minute window",
            "ETF rebalancing day increases likelihood of institutional flow",
        ],
        "risk_level": "Medium",
        "confidence": 0.78,
    },
    {
        "summary": (
            "TSLA volume anomaly detected near session close. Late-day spikes of "
            "this magnitude often correlate with MOC (market-on-close) order imbalances "
            "or algorithmic execution of large block trades."
        ),
        "reasons": [
            "Volume 6.1x above rolling average — highest spike in 24h window",
            "Spike occurred within 30 minutes of market close",
            "Bid-ask spread widened during spike, consistent with block trade execution",
            "Price recovered within 3 candles — temporary supply absorption",
        ],
        "risk_level": "High",
        "confidence": 0.88,
    },
]


# ── Candle generation ─────────────────────────────────────────────────────────


def _generate_candles() -> list[dict]:
    """Generate N_CANDLES of realistic TSLA 1-minute OHLCV data."""
    candles = []
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    price = BASE_PRICE

    for i in range(N_CANDLES):
        ts = now - timedelta(minutes=(N_CANDLES - i))

        # Random walk on price (±0.3%)
        change = random.uniform(-0.003, 0.003)
        open_ = round(price, 4)
        close = round(price * (1 + change), 4)
        high = round(max(open_, close) * random.uniform(1.0, 1.002), 4)
        low = round(min(open_, close) * random.uniform(0.998, 1.0), 4)

        if i in SPIKE_INDICES:
            volume = int(BASE_VOLUME * SPIKE_MULTIPLIER * random.uniform(0.9, 1.1))
        else:
            volume = int(BASE_VOLUME * random.uniform(0.6, 1.4))

        candles.append({
            "time": ts,
            "ticker": TICKER,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
        price = close

    return candles


# ── Anomaly + report helpers ──────────────────────────────────────────────────


def _zscore_for_spike(candles: list[dict], spike_idx: int) -> float:
    """Compute the actual z-score for a spike candle vs its 20-candle window."""
    window = candles[max(0, spike_idx - 20) : spike_idx]
    volumes = [c["volume"] for c in window]
    if len(volumes) < 2:
        return 0.0
    mean = sum(volumes) / len(volumes)
    variance = sum((v - mean) ** 2 for v in volumes) / len(volumes)
    std = variance ** 0.5
    if std == 0:
        return 0.0
    return (candles[spike_idx]["volume"] - mean) / std


# ── Main seed ─────────────────────────────────────────────────────────────────


async def seed() -> None:
    engine = create_async_engine(settings.async_database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    candles = _generate_candles()
    spike_list = sorted(SPIKE_INDICES)

    async with factory() as session:
        # ── 1. Insert candles ──────────────────────────────────────────────
        await session.execute(
            text("""
                INSERT INTO market_data (time, ticker, open, high, low, close, volume)
                VALUES (:time, :ticker, :open, :high, :low, :close, :volume)
                ON CONFLICT (time, ticker) DO NOTHING
            """),
            candles,
        )
        print(f"  Inserted {len(candles)} candles for {TICKER}")

        # ── 2. Insert anomalies + reports ──────────────────────────────────
        for order, (spike_idx, report_data) in enumerate(zip(spike_list, MOCK_REPORTS)):
            candle = candles[spike_idx]
            zscore = _zscore_for_spike(candles, spike_idx)
            severity = "HIGH" if zscore > 3.5 else "MEDIUM"

            anomaly_id = uuid.uuid4()
            detected_at = candle["time"] + timedelta(seconds=2)

            await session.execute(
                text("""
                    INSERT INTO anomalies
                      (id, detected_at, candle_time, ticker, type, severity,
                       zscore, iqr_flag, report_status)
                    VALUES
                      (:id, :detected_at, :candle_time, :ticker, 'volume_spike',
                       :severity, :zscore, false, 'completed')
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": anomaly_id,
                    "detected_at": detected_at,
                    "candle_time": candle["time"],
                    "ticker": TICKER,
                    "severity": severity,
                    "zscore": round(zscore, 4),
                },
            )

            report_id = uuid.uuid4()
            await session.execute(
                text("""
                    INSERT INTO reports
                      (id, anomaly_id, summary, reasons, risk_level,
                       confidence, tokens_used, latency_ms, created_at)
                    VALUES
                      (:id, :anomaly_id, :summary, cast(:reasons as jsonb), :risk_level,
                       :confidence, 0, 12, :created_at)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": report_id,
                    "anomaly_id": anomaly_id,
                    "summary": report_data["summary"],
                    "reasons": __import__("json").dumps(report_data["reasons"]),
                    "risk_level": report_data["risk_level"],
                    "confidence": report_data["confidence"],
                    "created_at": detected_at + timedelta(milliseconds=12),
                },
            )

            print(f"  Anomaly {order + 1}: {severity} z={zscore:.2f} at candle {spike_idx} → report created")

        await session.commit()

    await engine.dispose()
    print("\nSeed complete. Refresh the dashboard.")


if __name__ == "__main__":
    asyncio.run(seed())
