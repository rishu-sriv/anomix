"""
GET /api/v1/reports/{anomaly_id}

Returns the report for a given anomaly.  Possible responses:
  200  — ReportSchema       (report is completed)
  202  — ReportPendingSchema (report is still pending)
  200  — ReportFailedSchema  (report generation failed)
  404  — {error: "report_not_found"}

FastAPI will serialize with response_model=ReportSchema for the happy path.
The 202 and 404 branches use JSONResponse to set the correct status code.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.anomaly import ReportStatus
from app.repositories.anomaly_repo import AnomalyRepo
from app.repositories.report_repo import ReportRepo
from app.schemas.report import ReportFailedSchema, ReportPendingSchema, ReportSchema

router = APIRouter()


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
