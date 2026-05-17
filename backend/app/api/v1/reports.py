"""
Reports API — two endpoints:

GET /api/v1/reports/{anomaly_id}
    Returns the persisted report for a given anomaly.  Possible responses:
      200  — ReportSchema        (report is completed)
      202  — ReportPendingSchema (report is still pending)
      200  — ReportFailedSchema  (report generation failed)
      404  — {error: "report_not_found"}

GET /api/v1/reports/{anomaly_id}/stream
    SSE endpoint that streams a report token-by-token.
    If the report is already completed it pseudo-streams the existing summary.
    If the report is pending (and USE_MOCK_REPORTS=false) it opens a fresh
    Claude streaming call and emits tokens as they arrive.
    Does NOT write to DB — the Celery report task owns persistence.

    SSE event shapes:
      {"token": "<chunk>"}          — incremental text chunk
      {"done": true, "report": {…}} — final event with full report payload
      {"error": "<message>"}        — emitted on failure before the stream closes
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.anomaly import ReportStatus
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.market_repo import MarketRepo
from app.repositories.report_repo import ReportRepo
from app.schemas.report import ReportFailedSchema, ReportPendingSchema, ReportSchema
from app.services.reporter import generate_report, stream_report_tokens

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GET /reports/{anomaly_id} ─────────────────────────────────────────────────


@router.get("/reports/{anomaly_id}", response_model=ReportSchema)
async def get_report(
    anomaly_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReportSchema | JSONResponse:
    anomaly = await AnomalyRepo.get_by_id(session, anomaly_id)
    if anomaly is None:
        return JSONResponse(status_code=404, content={"error": "report_not_found"})

    if anomaly.report_status == ReportStatus.pending:
        pending = ReportPendingSchema(
            estimated_ready_at=datetime.now(tz=timezone.utc) + timedelta(seconds=30)
        )
        return JSONResponse(status_code=202, content=pending.model_dump(mode="json"))

    if anomaly.report_status == ReportStatus.failed:
        return JSONResponse(
            status_code=200, content=ReportFailedSchema().model_dump(mode="json")
        )

    report = await ReportRepo.get_by_anomaly_id(session, anomaly_id)
    if report is None:
        return JSONResponse(status_code=404, content={"error": "report_not_found"})

    return ReportSchema.model_validate(report)


# ── GET /reports/{anomaly_id}/stream ─────────────────────────────────────────


@router.get("/reports/{anomaly_id}/stream", response_model=None)
async def stream_report(
    anomaly_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse | JSONResponse:
    """
    SSE streaming endpoint.

    All DB reads happen synchronously in this handler (before returning
    StreamingResponse) so the injected session is used only for reads and
    is closed cleanly after the generator is exhausted.

    The generator captures plain-data snapshots of the ORM objects it needs,
    never making new DB calls itself.
    """
    from app.config import settings  # local import — avoids circular at module level

    anomaly = await AnomalyRepo.get_by_id(session, anomaly_id)
    if anomaly is None:
        return JSONResponse(status_code=404, content={"error": "report_not_found"})

    # Load context needed by the reporter (used in the real-streaming path)
    candles, _ = await MarketRepo.get_candles(session, anomaly.ticker, hours=1)
    stats = await MarketRepo.get_rolling_stats(session, anomaly.ticker)

    # Check for an already-completed report
    existing = await ReportRepo.get_by_anomaly_id(session, anomaly_id)
    existing_schema = ReportSchema.model_validate(existing) if existing is not None else None

    # ── Snapshot values for the generator closure ─────────────────────────────
    # We capture what we need as plain objects here — the ORM session remains
    # alive for the duration of the StreamingResponse but we never touch it
    # inside the async generator to avoid subtle expiry / thread-safety issues.
    _anomaly = anomaly
    _candles = list(candles)
    _stats = stats
    _use_mock = settings.use_mock_reports

    async def event_generator():  # type: ignore[return]
        # ── Case 1: report already completed → pseudo-stream existing text ────
        if existing_schema is not None:
            for word in existing_schema.summary.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.03)
            yield (
                f"data: {json.dumps({'done': True, 'report': existing_schema.model_dump(mode='json')})}\n\n"
            )
            return

        # ── Case 2: mock mode → generate mock synchronously, pseudo-stream ────
        if _use_mock:
            try:
                mock_report = generate_report(_anomaly, _candles, _stats)
            except Exception as exc:
                logger.error("Mock report generation failed for anomaly %s: %s", anomaly_id, exc)
                yield f"data: {json.dumps({'error': 'generation_failed'})}\n\n"
                return

            for word in mock_report.summary.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield (
                f"data: {json.dumps({'done': True, 'report': mock_report.model_dump(mode='json')})}\n\n"
            )
            return

        # ── Case 3: real streaming — call Claude and emit tokens live ─────────
        collected: list[str] = []
        start_time = time.monotonic()

        try:
            async for token in stream_report_tokens(_anomaly, _candles, _stats):
                collected.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.error(
                "SSE streaming failed for anomaly %s: %s", anomaly_id, exc
            )
            yield f"data: {json.dumps({'error': 'streaming_failed'})}\n\n"
            return

        # Parse the accumulated JSON from the stream
        full_text = "".join(collected).strip()
        try:
            # Strip markdown fences if Claude added them despite the system prompt
            if full_text.startswith("```"):
                lines = full_text.splitlines()
                end = -1 if (lines and lines[-1].strip() == "```") else len(lines)
                full_text = "\n".join(lines[1:end])

            data = json.loads(full_text)
            report_schema = ReportSchema(
                id=uuid.uuid4(),
                anomaly_id=anomaly_id,
                summary=str(data["summary"]),
                reasons=[str(r) for r in data["reasons"]],
                risk_level=str(data["risk_level"]),
                confidence=float(data["confidence"]),
                tokens_used=0,  # streaming API does not expose token counts mid-stream
                latency_ms=int((time.monotonic() - start_time) * 1000),
                created_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:
            logger.error(
                "SSE parse failed for anomaly %s: %s — raw: %.120s",
                anomaly_id,
                exc,
                full_text,
            )
            yield f"data: {json.dumps({'error': 'parse_failed'})}\n\n"
            return

        yield (
            f"data: {json.dumps({'done': True, 'report': report_schema.model_dump(mode='json')})}\n\n"
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering for SSE
        },
    )
