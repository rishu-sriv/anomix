"""
Report generation service — pure functions, zero database calls.

V1: USE_MOCK_REPORTS=true  → generate_report() returns a hardcoded mock immediately.
V2: USE_MOCK_REPORTS=false → calls the Claude API with 2-attempt JSON parse retry
                             and optional Langfuse tracing when real credentials exist.
    stream_report_tokens() → async generator for the SSE /stream endpoint.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.models.anomaly import Anomaly
from app.repositories.market_repo import RollingStats
from app.schemas.report import ReportSchema

logger = logging.getLogger(__name__)

# ── Langfuse — only activated when real (non-stub) credentials are present ────
# This prevents Langfuse from being initialised in test environments (stub keys)
# and avoids network calls / auth errors during CI.

_LANGFUSE_ACTIVE = (
    settings.langfuse_public_key not in ("pk-lf-stub", "")
    and settings.langfuse_secret_key not in ("sk-lf-stub", "")
)

_lf_context = None  # module-level reference; set below when active

if _LANGFUSE_ACTIVE:
    try:
        from langfuse.decorators import (  # type: ignore[import]
            langfuse_context as _lf_context,
            observe as _lf_observe,
        )
    except Exception as _lf_import_err:
        logger.warning("Langfuse import failed: %s — tracing disabled", _lf_import_err)
        _LANGFUSE_ACTIVE = False


# ── Mock report content (V1 / USE_MOCK_REPORTS=true) ─────────────────────────

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


# ── Claude prompts ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a quantitative financial analyst specialising in market microstructure "
    "and statistical anomaly detection. Analyse the market anomaly described below "
    "and generate a structured research report.\n\n"
    "You MUST respond with a valid JSON object only — no preamble, no markdown fences, "
    "no commentary outside the JSON.\n\n"
    "Required fields:\n"
    '  "summary"    — string, 2-3 sentences explaining the anomaly and its likely cause\n'
    '  "reasons"    — array of exactly 3 strings, each a specific contributing factor\n'
    '  "risk_level" — string, exactly one of: "High", "Medium", "Low"\n'
    '  "confidence" — number between 0.0 and 1.0 representing model confidence'
)

_RETRY_SYSTEM_PROMPT = (
    "You are a quantitative financial analyst. "
    "CRITICAL INSTRUCTION: Respond with ONLY a raw JSON object. "
    "No markdown, no code fences, no preamble, no explanation. Just the JSON. "
    'Required keys: "summary" (string), "reasons" (array of 3 strings), '
    '"risk_level" ("High"/"Medium"/"Low"), "confidence" (float 0-1).'
)

_MODEL = "claude-haiku-4-5-20251001"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_prompt(anomaly: Anomaly, candles: list, stats: RollingStats) -> str:
    """Build the user-turn prompt from anomaly context, candle data, and rolling stats."""
    zscore_str = f"{anomaly.zscore:.2f}" if anomaly.zscore is not None else "N/A"
    iqr_str = "yes" if anomaly.iqr_flag else "no"

    candle_ctx = ""
    if candles:
        c = candles[0]
        candle_ctx = (
            f"\nLatest candle:  open={c.open}  high={c.high}  "
            f"low={c.low}  close={c.close}  volume={int(c.volume):,}"
        )

    stats_ctx = ""
    if stats and stats.count >= 1:
        stats_ctx = (
            f"\nRolling stats ({stats.count} candles):  "
            f"mean_volume={stats.mean:,.0f}  std_volume={stats.std:,.0f}"
        )

    return (
        f"Anomaly detected for {anomaly.ticker} at {anomaly.detected_at.isoformat()}.\n"
        f"Anomaly type:  {anomaly.type.value}\n"
        f"Severity:      {anomaly.severity.value}\n"
        f"Z-score:       {zscore_str}\n"
        f"IQR price swing detected: {iqr_str}"
        f"{candle_ctx}"
        f"{stats_ctx}\n\n"
        "Generate a financial analysis report for this market anomaly."
    )


def _parse_claude_json(
    raw: str,
    anomaly: Anomaly,
    start: float,
    tokens_used: int,
) -> ReportSchema:
    """
    Parse Claude's text output into a ReportSchema.

    Strips optional markdown fences, then JSON-decodes and validates shape.
    Raises ValueError if required fields are missing or malformed.
    """
    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if Claude added them
    if text.startswith("```"):
        lines = text.splitlines()
        end = -1 if (lines and lines[-1].strip() == "```") else len(lines)
        text = "\n".join(lines[1:end])

    data: dict = json.loads(text)  # raises json.JSONDecodeError on bad JSON

    missing = {"summary", "reasons", "risk_level", "confidence"} - set(data)
    if missing:
        raise ValueError(f"Missing required fields in Claude response: {missing}")

    reasons = [str(r) for r in data["reasons"]]
    if len(reasons) != 3:
        raise ValueError(f"Expected exactly 3 reasons, got {len(reasons)}")

    return ReportSchema(
        id=uuid.uuid4(),
        anomaly_id=anomaly.id,
        summary=str(data["summary"]),
        reasons=reasons,
        risk_level=str(data["risk_level"]),
        confidence=float(data["confidence"]),
        tokens_used=tokens_used,
        latency_ms=int((time.monotonic() - start) * 1000),
        created_at=datetime.now(tz=timezone.utc),
    )


def _call_claude_with_retry(
    client: anthropic.Anthropic,
    prompt: str,
    anomaly: Anomaly,
    start: float,
) -> ReportSchema:
    """
    Call Claude and parse the response JSON.  Up to 2 attempts.
    Attempt 2 uses a stricter system prompt that forbids any non-JSON output.

    Raises RuntimeError if both attempts fail to produce parseable JSON.
    """
    total_tokens = 0
    systems = [_SYSTEM_PROMPT, _RETRY_SYSTEM_PROMPT]

    for attempt, system in enumerate(systems, start=1):
        try:
            response = client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            report = _parse_claude_json(raw, anomaly, start, total_tokens)

            logger.info(
                "Report generated for anomaly %s (attempt=%d tokens=%d latency=%dms)",
                anomaly.id,
                attempt,
                total_tokens,
                report.latency_ms,
            )
            return report

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            if attempt < len(systems):
                logger.warning(
                    "Parse attempt %d failed for anomaly %s: %s — retrying with stricter prompt",
                    attempt,
                    anomaly.id,
                    exc,
                )
            else:
                logger.error(
                    "Parse attempt %d (final) failed for anomaly %s: %s",
                    attempt,
                    anomaly.id,
                    exc,
                )
                raise RuntimeError(
                    f"Claude returned unparseable JSON after {len(systems)} attempts: {exc}"
                ) from exc

    # Unreachable — satisfies type-checker
    raise RuntimeError("Exhausted retry attempts without returning or raising")


# ── Public API ────────────────────────────────────────────────────────────────


def generate_report(
    anomaly: Anomaly,
    candles: list,
    stats: RollingStats,
) -> ReportSchema:
    """
    Generate a report for the given anomaly.

    USE_MOCK_REPORTS=true  → returns a hardcoded mock immediately (V1).
    USE_MOCK_REPORTS=false → calls the Claude API; traces via Langfuse when configured (V2).

    This function is synchronous and is called from the Celery report task via asyncio.run().
    Zero database calls — all inputs are passed by the caller.
    """
    start = time.monotonic()

    # ── Mock path ─────────────────────────────────────────────────────────────
    if settings.use_mock_reports:
        return ReportSchema(
            id=uuid.uuid4(),
            anomaly_id=anomaly.id,
            summary=_MOCK_SUMMARY,
            reasons=list(_MOCK_REASONS),
            risk_level=_MOCK_RISK_LEVEL,
            confidence=_MOCK_CONFIDENCE,
            tokens_used=0,
            latency_ms=int((time.monotonic() - start) * 1000),
            created_at=datetime.now(tz=timezone.utc),
        )

    # ── Real path — update Langfuse observation metadata if tracing is active ─
    if _LANGFUSE_ACTIVE and _lf_context is not None:
        try:
            _lf_context.update_current_observation(
                metadata={
                    "ticker": anomaly.ticker,
                    "severity": anomaly.severity.value,
                    "zscore": anomaly.zscore,
                    "anomaly_type": anomaly.type.value,
                    "anomaly_id": str(anomaly.id),
                }
            )
        except Exception:
            pass  # Never crash because of an observability call

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(anomaly, candles, stats)
    return _call_claude_with_retry(client, prompt, anomaly, start)


# Apply Langfuse @observe decorator only when real credentials are present.
# When _LANGFUSE_ACTIVE=False (stub keys / test environment) the function
# runs undecorated, which is faster and avoids network calls.
if _LANGFUSE_ACTIVE:
    try:
        generate_report = _lf_observe(name="generate_report")(generate_report)  # type: ignore[misc]
    except Exception as _dec_err:
        logger.warning("Failed to apply Langfuse decorator: %s", _dec_err)


async def stream_report_tokens(
    anomaly: Anomaly,
    candles: list,
    stats: RollingStats,
) -> AsyncGenerator[str, None]:
    """
    Async generator that streams Claude's response token-by-token.

    Yields raw text chunks as they arrive from the Anthropic streaming API.
    Used exclusively by the SSE /stream endpoint — never called from Celery tasks.

    Note: does not write to DB.  Persistence is the Celery task's responsibility.
    """
    async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(anomaly, candles, stats)

    async with async_client.messages.stream(
        model=_MODEL,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
