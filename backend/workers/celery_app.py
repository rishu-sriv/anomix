import os

from celery import Celery
from celery.schedules import crontab  # noqa: F401 — available for future cron-style schedules

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "finpulse",
    broker=redis_url,
    backend=redis_url,
    include=[
        "workers.ingestion_task",
        "workers.detection_task",
        "workers.report_task",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Prevent a single slow task from blocking the worker slot indefinitely.
    task_soft_time_limit=90,
    task_time_limit=120,
)

# ── Beat schedule ─────────────────────────────────────────────────────────────
# Fires ingest_market_data every 60 seconds per ticker.
# The ingestion task chains detect_anomalies when new candles are inserted,
# and detection chains generate_report when an anomaly is found.

app.conf.beat_schedule = {
    "ingest-tsla-every-60s": {
        "task": "workers.ingestion_task.ingest_market_data",
        "schedule": 60.0,
        "args": ("TSLA",),
    },
    "ingest-btcusd-every-60s": {
        "task": "workers.ingestion_task.ingest_market_data",
        "schedule": 60.0,
        "args": ("BTC-USD",),
    },
}
