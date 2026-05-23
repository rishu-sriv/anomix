"""
V2 API router — mounts all sub-routers under /api/v1.
"""

from fastapi import APIRouter

from app.api.v1 import anomalies, health, reports, stocks, ws

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])
router.include_router(stocks.router, tags=["stocks"])
router.include_router(anomalies.router, tags=["anomalies"])
router.include_router(reports.router, tags=["reports"])
router.include_router(ws.router, tags=["websocket"])
