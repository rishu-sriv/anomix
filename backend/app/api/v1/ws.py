"""
WebSocket endpoint — /api/v1/ws

Broadcasts report_ready events to all connected clients in real time.
The Redis pub/sub channel 'finpulse:reports' is already published by
workers/report_task.py after every successful report generation.

Architecture:
  Each WebSocket connection creates its own Redis pub/sub subscription.
  When a report_ready message arrives on the channel, it is forwarded
  to the browser client as a JSON string.

  Why per-connection subscriptions instead of a shared fan-out set:
    FastAPI runs in a single asyncio event loop. At dashboard scale
    (a handful of concurrent users) a per-connection subscriber is
    simpler and correct. If load ever requires multiple uvicorn workers,
    each worker already fans out correctly because each connection has
    its own subscription.

Reconnect responsibility: the browser client (useWebSocket.ts) handles
reconnect with exponential backoff — the server endpoint is stateless.

Payload shape published on the channel (from report_task.py):
  {"anomaly_id": "uuid", "status": "ready", "ticker": "TSLA", "severity": "HIGH"}
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

WS_CHANNEL = "finpulse:reports"


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Accept a WebSocket connection and subscribe it to the anomaly event channel.

    The connection stays alive until the client disconnects or an error occurs.
    Cleanup (unsubscribe + close Redis connection) happens in the finally block.
    """
    await websocket.accept()

    redis_client: aioredis.Redis = aioredis.from_url(
        settings.redis_url, decode_responses=True
    )
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(WS_CHANNEL)
    logger.info("WebSocket client connected — subscribed to %s", WS_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected cleanly")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        await pubsub.unsubscribe(WS_CHANNEL)
        await redis_client.aclose()
        logger.debug("WebSocket cleanup complete")
