"""
Demo seeder — inserts realistic TSLA candles, 3 anomalies with rich
root-cause reports, and sends a Langfuse trace for each report.

Run inside the backend container:
    docker exec finpulse_backend python seed_demo.py
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.langfuse_client import get_langfuse
from app.models.anomaly import AnomalyType, ReportStatus, Severity
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo

NOW = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)


# ── 1. Candle data ─────────────────────────────────────────────────────────────
# 30 one-minute candles ending ~1 minute ago.
# Candles 0-19  → normal baseline  (~610k mean volume)
# Candle  20    → EXTREME spike     (12.8M → z ≈ 19.5)  HIGH
# Candles 21-23 → post-spike normal
# Candle  24    → HIGH spike         (3.8M  → z ≈ 5.8)   HIGH
# Candles 25-27 → post-spike normal
# Candle  28    → MEDIUM spike       (2.1M  → z ≈ 3.2)   MEDIUM
# Candle  29    → final normal

PRICES = [
    176.32, 176.18, 175.94, 176.41, 176.85, 177.12, 177.04, 176.92,
    176.78, 177.23, 177.45, 177.38, 177.61, 177.82, 178.04, 178.19,
    178.05, 177.93, 178.22, 178.47,
    178.61, 178.58, 178.64, 178.71,
    178.88, 178.79, 178.93, 178.84,
    179.02, 179.11,
]

VOLUMES = [
    623441, 589234, 611872, 598443, 634219, 607881, 621543, 594328,
    618774, 628341, 603219, 615882, 622341, 598774, 631229, 609441,
    617882, 604329, 629118, 618443,
    12847392,                           # spike 1
    631229, 608441, 619882,
    3841200,                            # spike 2
    627118, 614329, 602881,
    2156800,                            # spike 3
    634219,
]

TIMES = [NOW - timedelta(minutes=(29 - i)) for i in range(30)]


def _candle_dict(i: int) -> dict:
    close = Decimal(str(PRICES[i]))
    return {
        "time":   TIMES[i],
        "ticker": "TSLA",
        "open":   Decimal(str(round(PRICES[i] * 0.9992, 4))),
        "high":   Decimal(str(round(PRICES[i] * 1.0018, 4))),
        "low":    Decimal(str(round(PRICES[i] * 0.9975, 4))),
        "close":  close,
        "volume": VOLUMES[i],
    }


# ── 2. Rich demo report content ────────────────────────────────────────────────

SPIKE_CONFIGS = [
    {
        "candle_idx": 20,
        "zscore": 19.50,
        "severity": Severity.HIGH,
        "summary": (
            "An exceptional volume anomaly was detected for TSLA, with trading activity "
            "reaching 19.5 standard deviations above the 20-candle rolling mean. This "
            "magnitude of deviation is consistent with major institutional block trades, "
            "dark pool activity surfacing on-exchange, or a significant news catalyst "
            "triggering a large-scale liquidity event at the $178 level."
        ),
        "reasons": [
            "Volume of 12,847,392 exceeded the 20-candle rolling average of 613,000 by "
            "19.5σ — a statistical event occurring less than once in 10⁸³ trading sessions "
            "under normal distribution assumptions, ruling out random noise entirely.",
            "The spike occurred without a corresponding price breakout (+0.08%), indicating "
            "absorption by institutional counterparties — consistent with market makers "
            "hedging a large notional derivative position at the $178 strike cluster.",
            "Block trade fingerprint: volume concentrated at candle open is characteristic "
            "of algorithmic execution of a scheduled institutional order, most likely an "
            "index rebalance basket or ETF creation/redemption flow.",
        ],
        "risk_level": "High",
        "confidence": 0.94,
    },
    {
        "candle_idx": 24,
        "zscore": 5.81,
        "severity": Severity.HIGH,
        "summary": (
            "TSLA experienced a significant volume surge 5.8 standard deviations above "
            "its rolling mean, indicating elevated institutional participation. The timing "
            "and contained price action suggest a coordinated execution pattern consistent "
            "with large-order algorithms distributing or accumulating near the $178.88 level."
        ),
        "reasons": [
            "Volume of 3,841,200 shares represents 6.3x the rolling average — a ratio "
            "historically associated with index rebalancing flows or ETF creation/redemption "
            "activity in large-cap equities with high passive ownership like TSLA.",
            "Price remained range-bound during the spike (+0.15%), suggesting a matched "
            "buyer-seller pair executing at mid-market — a hallmark of dark pool "
            "internalization surfacing on the primary exchange.",
            "Options open interest in the $178–$180 strike range increased 18% in the "
            "preceding session, signalling pre-positioned hedging activity by institutions "
            "anticipating an imminent directional move.",
        ],
        "risk_level": "High",
        "confidence": 0.89,
    },
    {
        "candle_idx": 28,
        "zscore": 3.21,
        "severity": Severity.MEDIUM,
        "summary": (
            "A moderate volume anomaly was detected for TSLA at 3.2 standard deviations "
            "above the rolling mean. While below the high-severity threshold, the gradual "
            "volume build across consecutive candles suggests algorithmic accumulation "
            "rather than a single large order — warranting close monitoring for follow-through."
        ),
        "reasons": [
            "Volume of 2,156,800 exceeded the rolling mean by 3.2σ, a level historically "
            "associated with retail momentum surges and social-sentiment-driven spikes "
            "in high-profile consumer names like TSLA.",
            "The gradual volume build across 3 consecutive candles — rather than a single "
            "burst — is characteristic of VWAP/TWAP execution algorithms scaling into a "
            "position to minimise market impact and avoid triggering exchange surveillance.",
            "EV sector macro uncertainty remains elevated; historical backtesting shows "
            "that TSLA volume anomalies at this σ level precede a directional move of "
            "2–4% within the following 48-hour window in 61% of cases.",
        ],
        "risk_level": "Medium",
        "confidence": 0.78,
    },
]


# ── 3. Seeder ──────────────────────────────────────────────────────────────────

async def seed() -> None:
    engine = create_async_engine(settings.async_database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    lf = get_langfuse()

    async with Session() as session:

        # ── Insert candles ─────────────────────────────────────────────────────
        print("Inserting 30 TSLA candles...")
        candle_dicts = [_candle_dict(i) for i in range(30)]
        inserted = await MarketRepo.upsert_candles(session, candle_dicts)
        print(f"  {inserted} new candles written (conflicts skipped)")

        # ── Create anomaly + report for each spike ─────────────────────────────
        for cfg in SPIKE_CONFIGS:
            candle_time = TIMES[cfg["candle_idx"]]
            detected_at = candle_time + timedelta(seconds=2)

            print(f"\nAnomaly @ {candle_time.strftime('%H:%M')} UTC — "
                  f"z={cfg['zscore']}  severity={cfg['severity'].value}")

            # -- Anomaly row ---------------------------------------------------
            anomaly = await AnomalyRepo.create(session, {
                "detected_at":   detected_at,
                "candle_time":   candle_time,
                "ticker":        "TSLA",
                "type":          AnomalyType.volume_spike,
                "severity":      cfg["severity"],
                "zscore":        cfg["zscore"],
                "iqr_flag":      False,
                "report_status": ReportStatus.pending,
            })
            print(f"  anomaly.id = {anomaly.id}")

            # -- Langfuse trace ------------------------------------------------
            t0 = time.monotonic()
            trace = lf.trace(
                name="generate_anomaly_report",
                input={
                    "ticker":      "TSLA",
                    "severity":    cfg["severity"].value,
                    "zscore":      cfg["zscore"],
                    "candle_time": candle_time.isoformat(),
                },
                metadata={
                    "mock":             True,
                    "use_mock_reports": True,
                    "anomaly_id":       str(anomaly.id),
                    "anomaly_type":     "volume_spike",
                },
            )
            latency_ms = int((time.monotonic() - t0) * 1000) + 14
            trace.update(
                output={
                    "summary":    cfg["summary"],
                    "risk_level": cfg["risk_level"],
                    "confidence": cfg["confidence"],
                },
                metadata={
                    "mock":             True,
                    "attempt_number":   1,
                    "use_mock_reports": True,
                    "tokens_used":      0,
                    "latency_ms":       latency_ms,
                    "parse_success":    True,
                },
            )

            # -- Report row ----------------------------------------------------
            report = await ReportRepo.create(session, {
                "anomaly_id":  anomaly.id,
                "summary":     cfg["summary"],
                "reasons":     cfg["reasons"],
                "risk_level":  cfg["risk_level"],
                "confidence":  cfg["confidence"],
                "tokens_used": 0,
                "latency_ms":  latency_ms,
                "created_at":  detected_at + timedelta(milliseconds=latency_ms),
            })
            print(f"  report.id  = {report.id}")

            # -- Mark anomaly completed ----------------------------------------
            await AnomalyRepo.update_report_status(
                session, anomaly.id, ReportStatus.completed
            )
            print(f"  status     → completed")

        await session.commit()

    # Flush Langfuse traces before process exits
    lf.flush()
    await engine.dispose()

    print("\n✓ Seed complete.")
    print("  Frontend  →  http://localhost:5173")
    print("  Langfuse  →  cloud.langfuse.com  (3 new traces)")


asyncio.run(seed())
