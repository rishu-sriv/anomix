"""
FinPulse MCP Server — exposes anomaly data as tools for Claude Desktop / agents.

Tools:
  list_anomalies  — query recent anomalies with optional filters
  get_report      — fetch the AI report for a specific anomaly
  get_health      — system health snapshot (last ingestion, 24h anomaly count)

Architecture:
  This server re-uses the same SQLAlchemy models and repositories as the
  FastAPI backend. It does NOT call the REST API — it queries the DB directly
  via the repository layer, following the same no-business-logic-in-repos rule.
  Settings come from the same .env file via pydantic-settings.

Running:
  python mcp_server/server.py

Claude Desktop config (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "finpulse": {
        "command": "python",
        "args": ["/absolute/path/to/mcp_server/server.py"],
        "env": {
          "DB_HOST": "localhost",
          "DB_PORT": "5432",
          "DB_NAME": "finpulse",
          "DB_USER": "postgres",
          "DB_PASSWORD": "your_password",
          "REDIS_URL": "redis://localhost:6379/0",
          "ANTHROPIC_API_KEY": "sk-ant-stub",
          "TICKERS": "TSLA,BTC-USD"
        }
      }
    }
  }
"""

from __future__ import annotations

import json
import sys
import uuid as uuid_module
from pathlib import Path

# Allow imports from the backend package without installing it as a pip package.
# This is appropriate for a standalone MCP script that shares code with the API.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from mcp.server.fastmcp import FastMCP  # type: ignore[import]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo

mcp = FastMCP("FinPulse")


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.async_database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Lazy-initialised session factory — avoids connecting until a tool is called.
_SessionFactory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = _make_session_factory()
    return _SessionFactory


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_anomalies(
    ticker: str | None = None,
    hours: int = 24,
    severity: str | None = None,
    limit: int = 20,
) -> str:
    """
    List recent anomalies detected by FinPulse.

    Args:
        ticker: Filter by ticker symbol (e.g. "TSLA", "BTC-USD"). Omit for all tickers.
        hours: Look-back window in hours (1-168). Default 24.
        severity: Filter by severity level ("LOW", "MEDIUM", "HIGH"). Omit for all severities.
        limit: Maximum number of results to return (1-100). Default 20.

    Returns JSON with an anomalies array and metadata.
    Each anomaly includes: id, ticker, type, severity, zscore, iqr_flag,
    detected_at, and report_status.
    """
    from app.models.anomaly import Severity as SeverityEnum

    severity_enum = None
    if severity is not None:
        try:
            severity_enum = SeverityEnum[severity.upper()]
        except KeyError:
            return json.dumps({"error": f"Invalid severity '{severity}'. Use LOW, MEDIUM, or HIGH."})

    clamped_hours = min(max(hours, 1), 168)
    clamped_limit = min(max(limit, 1), 100)

    async with get_session_factory()() as session:
        rows, has_more = await AnomalyRepo.get_recent(
            session,
            ticker=ticker,
            hours=clamped_hours,
            severity=severity_enum,
            limit=clamped_limit,
        )

    result = {
        "anomalies": [
            {
                "id": str(r.id),
                "ticker": r.ticker,
                "type": r.type.value,
                "severity": r.severity.value,
                "zscore": round(r.zscore, 3) if r.zscore is not None else None,
                "iqr_flag": r.iqr_flag,
                "detected_at": r.detected_at.isoformat(),
                "report_status": r.report_status.value,
            }
            for r in rows
        ],
        "count": len(rows),
        "has_more": has_more,
        "filters": {
            "ticker": ticker,
            "hours": clamped_hours,
            "severity": severity,
        },
    }
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_report(anomaly_id: str) -> str:
    """
    Fetch the AI-generated research report for a specific anomaly.

    Args:
        anomaly_id: UUID of the anomaly (from list_anomalies output).

    Returns the full report including summary, reasons (3 bullet points),
    risk_level, confidence score, and generation metadata.
    Returns an error object if the report is not found or anomaly_id is invalid.
    """
    try:
        aid = uuid_module.UUID(anomaly_id)
    except ValueError:
        return json.dumps({"error": f"Invalid UUID format: '{anomaly_id}'"})

    async with get_session_factory()() as session:
        # Check anomaly exists and get its report_status
        anomaly = await AnomalyRepo.get_by_id(session, aid)
        if anomaly is None:
            return json.dumps({"error": "anomaly_not_found", "anomaly_id": anomaly_id})

        if anomaly.report_status.value == "pending":
            return json.dumps({
                "status": "pending",
                "anomaly_id": anomaly_id,
                "message": "Report is still being generated. Try again in a few seconds.",
            })

        if anomaly.report_status.value == "failed":
            return json.dumps({
                "status": "failed",
                "anomaly_id": anomaly_id,
                "message": "Report generation failed for this anomaly.",
            })

        report = await ReportRepo.get_by_anomaly_id(session, aid)

    if report is None:
        return json.dumps({"error": "report_not_found", "anomaly_id": anomaly_id})

    return json.dumps({
        "anomaly_id": anomaly_id,
        "summary": report.summary,
        "reasons": report.reasons,
        "risk_level": report.risk_level,
        "confidence": report.confidence,
        "tokens_used": report.tokens_used,
        "latency_ms": report.latency_ms,
        "created_at": report.created_at.isoformat(),
    }, indent=2)


@mcp.tool()
async def get_health() -> str:
    """
    Get the current health status of the FinPulse system.

    Returns:
        - anomalies_24h: Number of anomalies detected in the last 24 hours
        - last_ingestion: ISO timestamp of the most recent market data candle
        - tickers_monitored: List of tickers currently being ingested
        - status: "ok" or "error"
    """
    try:
        async with get_session_factory()() as session:
            count_24h = await AnomalyRepo.count_last_24h(session)
            # Use the first configured ticker for last_ingestion check
            primary_ticker = settings.ticker_list[0] if settings.ticker_list else "TSLA"
            last_ingestion = await MarketRepo.get_latest_time(session, primary_ticker)

        return json.dumps({
            "status": "ok",
            "anomalies_24h": count_24h,
            "last_ingestion": last_ingestion.isoformat() if last_ingestion else None,
            "tickers_monitored": settings.ticker_list,
        }, indent=2)
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)}, indent=2)


if __name__ == "__main__":
    mcp.run()
