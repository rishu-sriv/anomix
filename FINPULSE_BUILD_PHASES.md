# FinPulse — Granular Build Phase Breakdown

> Read this before touching any code. Every task has a clear input, output, and done-when
> condition. Never move to the next task until the current one is verifiably complete.
> "It works on my machine" is not done. The done-when condition is done.

---

## V1 vs V2 — Feature Scope Reference

> Use this table before touching any phase. If a feature is listed as V2, do not
> implement it. Building V2 features during V1 scope creates code that conflicts with the
> simplified pipeline and costs time you don't have.

| Feature | V1 (current) | V2 (deferred) |
|---|---|---|
| **Tickers** | TSLA only — hardcoded | Multi-ticker via `TICKERS` env var |
| **Detection method** | Z-score only | Z-score + IQR (two-signal confirmation) |
| **Severity logic** | zscore > 3.5 = HIGH, ≥ 2.5 = MEDIUM, below 2.5 = no anomaly | Combined matrix using both zscore and IQR flag |
| **Report generation** | Hardcoded mock written to DB synchronously (`USE_MOCK_REPORTS=true`) | Real Claude API call with Langfuse tracing |
| **Report display** | REST `GET /api/v1/reports/{id}` — static completed text | SSE streaming, token-by-token as Claude generates |
| **Frontend updates** | TanStack Query `refetchInterval: 30000` (REST polling) | WebSocket push from Redis Pub/Sub |
| **TradingView chart** | Not included | Candlestick chart with anomaly markers |
| **Toast notifications** | Not included | Sonner toast on HIGH severity WebSocket events |
| **LiveIndicator** | Not included | Pulsing dot showing WebSocket connection state |
| **MCP server** | Skipped entirely (Phase 7) | Claude Desktop integration with 3 tools |
| **Langfuse tracing** | Not included (Phase 3 skipped) | Full trace per Claude call |

**How to read this:** V1 is a working, deployable product. Every V1 feature above is
fully implemented and tested. V2 features are not stubs — they simply do not exist yet.
When moving to V2, implement each feature from scratch following the phase tasks marked
SKIPPED IN V1.

---

## How to use this document

Each phase has tasks. Each task has:
- **What you're doing** — the actual work
- **Why** — the reasoning so you can explain it in interviews
- **Done when** — a concrete, checkable condition. Not "I think it works."

If you're stuck on a task for more than 2 hours, the problem is almost always in a previous
task's done-when condition that you skipped. Go back and verify it.

---

## Phase 0 — Foundation
**Time estimate: 4–6 hours**
**Goal: A running skeleton that proves all 6 services can talk to each other. Zero features.**

This phase blocks everything. Do not start Phase 1 until every done-when here is green.

---

### Task 0.1 — Write ARCHITECTURE.md

**What you're doing:** Document every major tech decision BEFORE writing code. Forces you
to think through the system before you're committed to wrong choices.

**Contents to cover:**
- Why Celery over asyncio background tasks
- Why TimescaleDB over plain Postgres
- Why Redis Pub/Sub as the event bus
- Why TanStack Query + Zustand separation
- Why Zod as single source of truth
- Why two-signal anomaly detection (Z-score + IQR)

**Done when:** File exists at `ARCHITECTURE.md` with all 6 decisions written out in your
own words with reasoning. If you can't write the reasoning, you don't understand it yet —
go back to the architecture document and re-read.

---

### Task 0.2 — Write api-contracts.md

**What you're doing:** Lock the API contracts before writing a single route. Frontend and
backend will both implement against this document. If it's not written down first, the
contracts will drift.

**Contents:**
- Every route: method, path, query params, request body, all possible responses with HTTP codes
- WebSocket message types with full JSON shapes
- Cursor pagination behavior
- Error response format

**Done when:** File exists at `api-contracts.md`. Every route from your CLAUDE.md is
represented. No route shape should be decided later — decide it now.

---

### Task 0.3 — Create the full folder structure in one shot

**What you're doing:** Create every folder from your CLAUDE.md structure at once. Empty
folders with `.gitkeep` files. Do not create any real files yet — just the skeleton.

```bash
# Run this from the project root
mkdir -p backend/app/api/v1
mkdir -p backend/app/core
mkdir -p backend/app/models
mkdir -p backend/app/schemas
mkdir -p backend/app/repositories
mkdir -p backend/app/services
mkdir -p backend/workers
mkdir -p backend/migrations/versions
mkdir -p backend/tests
mkdir -p frontend/src/app
mkdir -p frontend/src/pages
mkdir -p frontend/src/features/chart
mkdir -p frontend/src/features/anomalies
mkdir -p frontend/src/features/reports
mkdir -p frontend/src/features/watchlist
mkdir -p frontend/src/components/ui
mkdir -p frontend/src/lib
mkdir -p mcp_server/tools
mkdir -p infra/nginx
mkdir -p infra/db
mkdir -p .github/workflows
```

**Done when:** Running `find . -type d | grep -v node_modules | grep -v .git` shows all
34 folders. Nothing more, nothing less.

---

### Task 0.4 — Write docker-compose.yml with all 6 services

**What you're doing:** Define all 6 services: timescaledb, redis, backend, worker, beat,
frontend. Include health checks on every service. Include `depends_on` with `condition:
service_healthy` so services start in the correct order.

**The 6 services and their roles:**

| Service | Image/Build | Role |
|---|---|---|
| timescaledb | timescale/timescaledb:latest-pg16 | Database |
| redis | redis:7-alpine | Task broker + event bus |
| backend | ./backend/Dockerfile | FastAPI API server |
| worker | ./backend/Dockerfile | Celery worker process |
| beat | ./backend/Dockerfile | Celery Beat scheduler |
| frontend | ./frontend/Dockerfile | React dev server |

**Critical details:**
- TimescaleDB health check: `pg_isready -U postgres`
- Redis health check: `redis-cli ping`
- Backend health check: `curl -f http://localhost:8000/api/v1/health`
- worker and beat use the same Dockerfile as backend but different `command` overrides
- All services share one Docker network

**Done when:** `docker compose config` runs without errors (validates the YAML). All
service names, health checks, and depends_on conditions are present.

---

### Task 0.5 — Write minimal Dockerfiles

**What you're doing:** Backend Dockerfile (Python 3.12 slim base, copies
requirements.txt, pip installs, copies app). Frontend Dockerfile (Node 20 alpine base,
npm install, dev server). These are NOT production-optimized yet — just enough to build.

**Done when:** `docker compose build` completes without errors for all 6 services. Images
exist in `docker images`.

---

### Task 0.6 — Write .env.example and Makefile

**.env.example** — every environment variable documented with a description, never a real
value. If a variable is missing here, it will be missing in production and the app will
fail silently.

```
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finpulse
DB_USER=postgres
DB_PASSWORD=your_password_here

# Redis
REDIS_URL=redis://localhost:6379/0

# AI + Observability
ANTHROPIC_API_KEY=sk-ant-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# App config
TICKERS=AAPL,TSLA,NVDA,MSFT,GOOGL
ANOMALY_ZSCORE_THRESHOLD=2.5
ALERT_SEVERITY_THRESHOLD=HIGH
USE_MOCK_REPORTS=true
BACKEND_URL=http://localhost:8000

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/api/v1/ws
```

**Makefile targets:**

```makefile
dev:        # docker compose up --build
build:      # docker compose build
test:       # pytest + tsc --noEmit
migrate:    # alembic upgrade head
migration:  # alembic revision --autogenerate -m "$(name)"
lint:       # ruff + mypy + tsc --noEmit
logs:       # docker compose logs -f
shell:      # docker compose exec backend python
db:         # docker compose exec timescaledb psql -U postgres finpulse
down:       # docker compose down
```

**Done when:** `make dev` starts all 6 containers. All 6 show as healthy in
`docker compose ps`. `make down` stops them cleanly.

---

### Task 0.7 — Write GitHub Actions CI pipeline

**What you're doing:** CI runs on every push to any branch. Four jobs must pass: ruff
(Python linting), mypy (Python type checking), pytest (backend tests), tsc (frontend type
checking). Fail fast — if ruff fails, don't run the others.

**Done when:** Push an empty commit to GitHub. CI pipeline runs and all 4 jobs pass (they
will pass trivially since there's no code yet). Green checkmark on the commit.

---

### Task 0.8 — Set up branch protection

**What you're doing:** In GitHub repo settings, require CI to pass before merging to main.
This forces you to keep the codebase always in a working state.

**Done when:** Try pushing directly to main — it should be rejected. Create a branch,
push, open a PR — CI runs and must pass before merge is allowed.

---

### Phase 0 — Complete done-when

- [ ] `ARCHITECTURE.md` exists with all 6 decisions written in your own words
- [ ] `api-contracts.md` exists with every route documented
- [ ] All 34 folders exist in the correct structure
- [ ] `make dev` starts 6 healthy containers
- [ ] `make down` stops them cleanly
- [ ] CI pipeline runs and is green on GitHub
- [ ] Branch protection is active on main

---

## Phase 1 — Database
**Time estimate: 6–8 hours**
**Goal: Schema exists, migrations run, hypertable is created, continuous aggregate works,
repositories are tested against a real DB.**

---

### Task 1.1 — Write init.sql for TimescaleDB setup

**What you're doing:** This file runs once when the TimescaleDB container first starts.
It handles everything Alembic cannot: creating the hypertable, continuous aggregate,
compression policy, and indexes.

**Contents of `infra/db/init.sql`:**

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert market_data to a hypertable (done AFTER Alembic creates the table)
-- This is called manually after first migration, not in this file
-- This file only creates the extension and any manual setup

-- Continuous aggregate for rolling stats
-- (Called after hypertable exists — see Task 1.3)
```

**Why init.sql and not Alembic:** Alembic manages regular DDL (CREATE TABLE, ALTER TABLE).
TimescaleDB commands like `create_hypertable()` and `CREATE MATERIALIZED VIEW ... WITH
(timescaledb.continuous)` are not standard SQL — Alembic doesn't know about them and will
fail or ignore them. They go in init.sql which runs at container startup.

**Done when:** init.sql file exists. `make db` connects to psql and `\dx` shows the
timescaledb extension is installed.

---

### Task 1.2 — Write SQLAlchemy models

**What you're doing:** Three models using SQLAlchemy 2.0 `mapped_column()` syntax.

**`models/market_data.py`:**
```python
class MarketData(Base):
    __tablename__ = "market_data"
    
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

**`models/anomaly.py`:**
```python
class AnomalyType(enum.Enum):
    volume_spike = "volume_spike"
    price_swing = "price_swing"

class Severity(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ReportStatus(enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    type: Mapped[AnomalyType] = mapped_column(Enum(AnomalyType))
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    zscore: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iqr_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    report_status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus), default=ReportStatus.pending
    )
```

**`models/report.py`:**
```python
class Report(Base):
    __tablename__ = "reports"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    anomaly_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("anomalies.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    reasons: Mapped[list] = mapped_column(JSONB)        # string array
    risk_level: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float)
    tokens_used: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

**Why NUMERIC(12,4) not FLOAT:** Floats have rounding errors in binary representation.
`182.5` stored as a float may come back as `182.49999999998`. In financial data shown
to users this is a bug. NUMERIC is exact decimal arithmetic.

**Done when:** All three model files exist. No import errors when running
`python -c "from app.models import MarketData, Anomaly, Report"`.

---

### Task 1.3 — Write and run Alembic migrations

**What you're doing:** Initialize Alembic, configure it to use your async SQLAlchemy
engine, generate the initial migration from your models, and run it.

**Steps:**
1. `alembic init migrations` in the backend directory
2. Configure `alembic.ini` with your DB URL
3. Configure `migrations/env.py` to import your Base and use async engine
4. `alembic revision --autogenerate -m "initial schema"` — generates migration file
5. Review the generated file — confirm it creates all 3 tables with correct column types
6. `alembic upgrade head` — runs the migration

**After migration runs, convert market_data to a hypertable manually:**
```sql
SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');
```

**Then create the continuous aggregate:**
```sql
CREATE MATERIALIZED VIEW market_data_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    ticker,
    AVG(volume) AS avg_volume,
    STDDEV(volume) AS std_volume,
    AVG((close - open) / open * 100) AS avg_price_change,
    STDDEV((close - open) / open * 100) AS std_price_change,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY (close - open) / open * 100) AS q1_price_change,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY (close - open) / open * 100) AS q3_price_change
FROM market_data
GROUP BY bucket, ticker;

-- Refresh policy: update the aggregate every 5 minutes
SELECT add_continuous_aggregate_policy('market_data_stats',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes');

-- Compression: compress data older than 7 days
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker'
);
SELECT add_compression_policy('market_data', INTERVAL '7 days');
```

**Done when:** `make migrate` runs without errors. `make db` then `\dt` shows all 3
tables. `SELECT * FROM timescaledb_information.hypertables` shows market_data. The
continuous aggregate `market_data_stats` exists as a view.

---

### Task 1.4 — Write Pydantic v2 schemas

**What you're doing:** Pydantic schemas are NOT the same as SQLAlchemy models. Models
define the DB table. Schemas define what goes in and out of the API. They are separate
deliberately.

**`schemas/market.py`:** CandleSchema (response), CandleListResponse (paginated)

**`schemas/anomaly.py`:** AnomalySchema (response), AnomalyListResponse (paginated),
AnomalyEventSchema (WebSocket event)

**`schemas/report.py`:** ReportSchema (completed), ReportPendingSchema (202),
ReportFailedSchema (failed)

**Every schema must use `model_config = ConfigDict(from_attributes=True)`** — this allows
`ReportSchema.model_validate(orm_object)` to work without manual mapping.

**Done when:** Import all schemas with no errors. Run `python -c "from app.schemas import
*"`. Zero errors.

---

### Task 1.5 — Write repositories

**What you're doing:** All database queries live here and ONLY here. No queries in
services, no queries in routes. Three repository classes, one per model.

**`repositories/market_repo.py`:**
- `upsert_candles(candles: list[CandleInsert]) -> int` — bulk upsert, returns rows inserted
- `get_candles(ticker, hours, cursor, limit) -> tuple[list[MarketData], str | None]`
- `get_rolling_stats(ticker) -> RollingStats | None` — queries `market_data_stats` view, NOT market_data

**`repositories/anomaly_repo.py`:**
- `create(anomaly: AnomalyCreate) -> Anomaly`
- `get_recent(ticker, hours, severity, type, cursor, limit) -> tuple[list[Anomaly], str | None]`
- `get_by_id(anomaly_id) -> Anomaly | None`
- `update_report_status(anomaly_id, status: ReportStatus) -> None`

**`repositories/report_repo.py`:**
- `create(report: ReportCreate) -> Report`
- `get_by_anomaly_id(anomaly_id) -> Report | None`

**Critical: `get_rolling_stats` must query `market_data_stats` view, never raw
`market_data`.** This is why TimescaleDB exists — querying the raw table for rolling
stats defeats the entire purpose.

**Done when:** All 3 repository files exist. All methods have type annotations. No
business logic inside any method — only SQL queries and return statements.

---

### Task 1.6 — Write repository tests

**What you're doing:** Test every repository method against a REAL test database. Not
mocks. A test database that spins up, runs your schema, executes real SQL, and tears down.

**`tests/conftest.py`:**
```python
@pytest.fixture(scope="session")
async def test_db():
    # Create a test database
    # Run alembic migrations against it
    # Create hypertable
    # Yield engine
    # Drop test database after session

@pytest.fixture
async def db_session(test_db):
    # Yield a fresh session for each test
    # Rollback after each test (no committed data between tests)

@pytest.fixture
def sample_candles():
    # 200 rows of synthetic OHLCV data with known anomaly at position 150
    # Used to seed tests that need data
```

**Tests to write:**
- `test_repos.py::test_upsert_candles_inserts_new_rows`
- `test_repos.py::test_upsert_candles_ignores_duplicates` (idempotency)
- `test_repos.py::test_get_candles_returns_paginated_results`
- `test_repos.py::test_create_anomaly_and_retrieve_by_id`
- `test_repos.py::test_update_report_status`
- `test_repos.py::test_create_report_linked_to_anomaly`

**Done when:** `pytest tests/test_repos.py -v` shows all tests passing with a real
database. Zero skipped tests.

---

### Task 1.7 — Write config.py

**What you're doing:** All environment variables in one place using pydantic-settings.
If a required variable is missing, the app crashes LOUDLY on startup with a clear error
message — not silently at runtime when the variable is first accessed.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str
    redis_url: str
    anthropic_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    tickers: list[str]   # parsed from comma-separated string
    anomaly_zscore_threshold: float = 2.5
    use_mock_reports: bool = True
    backend_url: str = "http://localhost:8000"
    
    model_config = ConfigDict(env_file=".env")

settings = Settings()
```

**Done when:** `python -c "from app.config import settings; print(settings.tickers)"` with
a valid `.env` file prints the tickers list. Running without `.env` raises a clear
`ValidationError` naming the missing fields.

---

### Phase 1 — Complete done-when

- [ ] `make migrate` runs clean against a fresh container
- [ ] All 3 tables exist in the DB with correct column types
- [ ] `market_data` is a hypertable (verify with timescaledb_information.hypertables)
- [ ] `market_data_stats` continuous aggregate view exists
- [ ] `pytest tests/test_repos.py -v` — all tests pass against real DB
- [ ] `python -c "from app.models import *; from app.schemas import *"` — zero import errors

---

## Phase 2 — Ingestion + Detection Workers
**Time estimate: 8–10 hours**
**Goal: TSLA data flows from yfinance into TimescaleDB. Anomalies are detected using
Z-score only and written to DB. Mock reports are written to DB synchronously. The full
detection pipeline works end-to-end without the API.**

> V1 simplifications applied to this phase:
> - Ingestion fetches TSLA only — no multi-ticker batch logic
> - Detector implements Z-score only — all IQR functions removed
> - Severity: zscore > 3.5 = HIGH, zscore ≥ 2.5 = MEDIUM, below 2.5 = no anomaly
> - Report task writes a hardcoded mock report to DB immediately — no Claude call

---

### Task 2.1 — Set up Celery app

**What you're doing:** Configure the Celery application with Redis as the broker, define
the Beat schedule, and set up task routing.

**`workers/celery_app.py`:**
```python
from celery import Celery
from celery.schedules import crontab

app = Celery(
    "finpulse",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.ingestion_task", "workers.detection_task", "workers.report_task"]
)

app.conf.beat_schedule = {
    "ingest-every-minute": {
        "task": "workers.ingestion_task.ingest_market_data",
        "schedule": 60.0,   # every 60 seconds
    }
}

app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"
```

**Done when:** `celery -A workers.celery_app worker --loglevel=info` starts without errors.
Celery connects to Redis successfully. Log shows "Connected to redis://..."

---

### Task 2.2 — Write the ingestion task

**What you're doing:** The task that fires every 60 seconds. Fetches TSLA data from
yfinance, parses the DataFrame, filters to new candles only, and upserts into TimescaleDB.

**V1 constraint:** TSLA is hardcoded. There is no multi-ticker batch call, no MultiIndex
DataFrame parsing, and no per-ticker Redis tracking for multiple tickers. One ticker, one
call, one chain.

**`workers/ingestion_task.py`:**

Key implementation details:
- Single `yf.download("TSLA", ...)` call — no `Tickers` object, no MultiIndex
- Columns are flat: `df["Close"]`, `df["Volume"]`, etc. — access directly
- Track last ingestion time for TSLA in Redis to filter out already-seen candles
- Drop rows where volume is NaN (yfinance returns NaN for incomplete candles)
- Drop rows where OHLC are all identical (stale/duplicated rows yfinance sometimes returns)
- Upsert with `ON CONFLICT (time, ticker) DO NOTHING` — never plain INSERT
- Market hours guard: skip task entirely outside 9:30am–4:00pm ET Monday–Friday
- After successful upsert: chain `detect_anomalies.si("TSLA")`

**Market hours guard:**
```python
from datetime import datetime
import pytz

def is_market_open() -> bool:
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
```

**Retry configuration:**
```python
@app.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_market_data(self):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        # 30s → 60s → 120s backoff
```

**Done when:** Trigger the task manually with `celery -A workers.celery_app call
workers.ingestion_task.ingest_market_data`. Check the DB: `SELECT COUNT(*) FROM
market_data WHERE ticker = 'TSLA'`. Rows should be present. Running it a second time
should not increase the count (idempotency check).

---

### Task 2.3 — Write the detector service (pure functions, Z-score only)

**What you're doing:** The core anomaly detection logic. Pure functions — no database
calls, no side effects. V1 uses Z-score only. IQR detection is deferred to V2.

**`services/detector.py`:**

```python
from dataclasses import dataclass, field
from typing import Optional

ZSCORE_THRESHOLD = 2.5

@dataclass
class RollingStats:
    avg_volume: float
    std_volume: float
    avg_price_change: float
    std_price_change: float
    q1_price_change: float   # retained for schema compatibility; not used in V1
    q3_price_change: float   # retained for schema compatibility; not used in V1

@dataclass
class DetectionResult:
    is_anomaly: bool
    anomaly_type: Optional[str]   # "volume_spike" | None
    severity: Optional[str]       # "MEDIUM" | "HIGH" | None
    zscore: Optional[float]
    iqr_flag: bool = False        # always False in V1; field retained for DB schema compatibility

def detect_volume_zscore(current_volume: int, stats: RollingStats) -> tuple[float, bool]:
    """
    Returns (zscore, is_above_threshold).
    zscore = (current - mean) / std
    Threshold: 2.5 standard deviations above mean.
    """
    if stats.std_volume == 0:
        return 0.0, False
    zscore = (current_volume - stats.avg_volume) / stats.std_volume
    return zscore, zscore >= ZSCORE_THRESHOLD

def determine_severity(zscore: float) -> Optional[str]:
    """
    V1 severity — Z-score only:
    zscore > 3.5  → HIGH
    zscore >= 2.5 → MEDIUM
    below 2.5     → None (no anomaly)

    IQR-based severity matrix is deferred to V2.
    """
    if zscore > 3.5:
        return "HIGH"
    elif zscore >= ZSCORE_THRESHOLD:
        return "MEDIUM"
    return None

def run_detection(candle: dict, stats: RollingStats) -> DetectionResult:
    """
    Main entry point. Takes one candle + rolling stats, returns DetectionResult.
    V1: Z-score only. IQR detection is deferred to V2.
    """
    zscore, volume_spike = detect_volume_zscore(candle["volume"], stats)
    severity = determine_severity(zscore)

    return DetectionResult(
        is_anomaly=severity is not None,
        anomaly_type="volume_spike" if volume_spike else None,
        severity=severity,
        zscore=zscore,
        iqr_flag=False   # V1: IQR not implemented
    )
```

**Why pure functions:** Services have no side effects — they receive data and return
results. The Celery task handles all DB reads/writes around the service call. This means
the detection logic can be unit tested with zero database, zero mocking, zero infrastructure.

**Done when:** `python -c "from app.services.detector import run_detection"` imports
without error. No database imports anywhere in the file. No IQR functions anywhere in
the file.

---

### Task 2.4 — Write detector unit tests (Z-score only)

**What you're doing:** At least 8 unit tests covering every Z-score edge case. These tests
run in milliseconds — no database, no network, no Docker required. Just Python.

**V1 constraint:** All IQR test cases are removed. Tests cover Z-score thresholds and
the simplified severity matrix only.

**`tests/test_detector.py`** — required test cases:

```
test_no_anomaly_on_normal_data
    Input: volume at exactly the mean (zscore = 0)
    Expected: DetectionResult(is_anomaly=False, severity=None)

test_volume_spike_detected_above_threshold
    Input: volume = mean + (3 * std)  # zscore = 3.0, above 2.5 threshold
    Expected: is_anomaly=True, anomaly_type="volume_spike", severity="MEDIUM"

test_borderline_volume_just_below_threshold
    Input: volume = mean + (2.4 * std)  # zscore = 2.4, just below 2.5
    Expected: is_anomaly=False, severity=None

test_borderline_volume_just_above_threshold
    Input: volume = mean + (2.6 * std)  # zscore = 2.6, just above 2.5
    Expected: is_anomaly=True, severity="MEDIUM"

test_zscore_exactly_at_threshold_is_medium
    Input: volume such that zscore = exactly 2.5
    Expected: is_anomaly=True, severity="MEDIUM"

test_zscore_above_3_5_is_high
    Input: volume = mean + (4 * std)  # zscore = 4.0
    Expected: severity="HIGH"

test_zscore_between_2_5_and_3_5_is_medium
    Input: volume = mean + (3.0 * std)  # zscore = 3.0
    Expected: severity="MEDIUM"

test_zero_std_returns_no_anomaly
    Input: stats with std_volume=0 (no variance in data)
    Expected: zscore=0.0, is_anomaly=False — no ZeroDivisionError raised

test_all_identical_volumes
    Input: std_volume=0 (flat line, all candles same volume)
    Expected: no anomaly, no ZeroDivisionError

test_iqr_flag_always_false
    Input: any candle + any stats
    Expected: DetectionResult.iqr_flag is always False in V1
```

**Done when:** `pytest tests/test_detector.py -v` shows 10 tests passing. Zero database
connections made during this test run. No IQR test cases present anywhere in the file.

---

### Task 2.5 — Write the detection task

**What you're doing:** The Celery task that wires the detector service to the database
and Redis. It reads data, calls pure functions, writes results.

**`workers/detection_task.py`:**

```python
@app.task
async def detect_anomalies(ticker: str):
    async with get_db_session() as session:
        # 1. Get rolling stats from continuous aggregate (NOT raw market_data)
        stats = await market_repo.get_rolling_stats(ticker, session)
        if stats is None:
            logger.warning(f"No rolling stats for {ticker} — skipping detection")
            return
        
        # 2. Get the most recent candle
        candles, _ = await market_repo.get_candles(ticker, hours=1, limit=1, session=session)
        if not candles:
            return
        
        candle = candles[0]
        
        # 3. Run detection (pure function — no DB calls inside)
        result = run_detection(candle.__dict__, stats)
        
        if not result.is_anomaly:
            return
        
        # 4. Write anomaly to DB
        anomaly = await anomaly_repo.create(AnomalyCreate(
            ticker=ticker,
            candle_time=candle.time,
            type=result.anomaly_type,
            severity=result.severity,
            zscore=result.zscore,
            iqr_flag=result.iqr_flag
        ), session)
        
        # 5. Publish to Redis for WebSocket broadcast
        await redis_client.publish(
            "finpulse:anomalies",
            AnomalyEventSchema.model_validate(anomaly).model_dump_json()
        )
        
        # 6. Chain report generation
        generate_report.si(str(anomaly.id)).delay()
```

**Done when:** Seed 2 weeks of historical TSLA data, run `CALL
refresh_continuous_aggregate('market_data_stats', NULL, NULL)` in psql, then trigger
detection manually. Check the anomalies table. You should see 2–8 anomalies per week.
If you see hundreds, your threshold is too low. If you see zero, your continuous
aggregate hasn't refreshed — run the manual refresh call.

---

### Task 2.6 — Write the report task (V1: mock report written to DB)

**What you're doing:** The report task that fires after every anomaly. In V1 with
`USE_MOCK_REPORTS=true`, this task writes a hardcoded mock report to the database
immediately and marks the anomaly as completed. No Claude call, no network request.

**V1 constraint:** This is not a logging stub — it writes a real row to the `reports`
table and sets `report_status = "completed"` on the anomaly. The GET /api/v1/reports/{id}
endpoint will return this data immediately when the frontend polls.

**`workers/report_task.py`:**

```python
@app.task
async def generate_report(anomaly_id: str):
    async with get_db_session() as session:
        anomaly = await anomaly_repo.get_by_id(uuid.UUID(anomaly_id), session)
        if anomaly is None:
            logger.error(f"Anomaly {anomaly_id} not found — skipping report generation")
            return

        # Idempotency check — don't write a second report if task retries
        existing = await report_repo.get_by_anomaly_id(anomaly.id, session)
        if existing is not None:
            logger.info(f"Report already exists for {anomaly_id}, skipping")
            return

        # V1: hardcoded mock report — no Claude call
        await report_repo.create(ReportCreate(
            anomaly_id=anomaly.id,
            summary=(
                f"Automated analysis: {anomaly.ticker} recorded a statistically significant "
                f"volume deviation (Z-score: {anomaly.zscore:.2f}) relative to its 20-period "
                f"rolling mean. This qualifies as a {anomaly.severity.value} severity anomaly "
                f"under the current detection threshold."
            ),
            reasons=[
                f"Volume Z-score of {anomaly.zscore:.2f} exceeded the detection threshold of 2.5",
                "Deviation is statistically significant relative to the rolling baseline",
                "No confounding signals evaluated in V1 — single-signal Z-score detection",
            ],
            risk_level=anomaly.severity.value.capitalize(),
            confidence=0.70,
            tokens_used=0,
            latency_ms=0,
        ), session)

        await anomaly_repo.update_report_status(anomaly.id, ReportStatus.completed, session)
        logger.info(f"Mock report written for anomaly {anomaly_id}")
```

**Done when:** Full pipeline runs without errors — ingestion → detection → report task.
Check the `reports` table: a row exists for the anomaly with a non-empty `summary` and
a `reasons` array. Check the `anomalies` table: `report_status` is `"completed"`. No
task failures in Celery logs.

---

### Phase 2 — Complete done-when

- [ ] `celery -A workers.celery_app worker` starts and connects to Redis
- [ ] Manual ingestion task call inserts TSLA rows into market_data
- [ ] Second call doesn't insert duplicates (idempotency)
- [ ] `pytest tests/test_detector.py -v` — 10 tests passing, zero DB connections, Z-score only cases, no IQR tests
- [ ] Full chain: ingestion → detection → report task — runs without errors
- [ ] Report row exists in DB with `report_status = "completed"` after full chain runs
- [ ] 2–8 TSLA anomalies visible in DB after seeding + detection run

---

## Phase 3 — AI Report Generation
**SKIPPED IN V1 — Deferred to V2**

> In V1, `USE_MOCK_REPORTS=true` is always set. The report task (Task 2.6) writes a
> hardcoded mock report to the database immediately after anomaly detection — no Claude
> API call is made, no Langfuse traces are emitted, no SSE stream exists.
>
> Phase 3 is the full V2 implementation. It covers:
> - Real Claude API call with structured JSON parsing (`services/reporter.py`)
> - Two-attempt parse-retry logic with stricter prompt on second attempt
> - Langfuse tracing (tokens, latency, ticker, severity per call)
> - SSE streaming endpoint (`GET /api/v1/reports/{id}/stream`) returning tokens progressively
>
> **Do not implement Phase 3 until V2 work begins. All four tasks below are deferred.**
> When V2 is ready, implement Phase 3 in full and set `USE_MOCK_REPORTS=false` only after
> all done-when conditions below pass.

---

### Task 3.1 — Write the reporter service
**SKIPPED IN V1**

The reporter service (`services/reporter.py`) builds the Claude prompt from anomaly +
candle context, calls the Anthropic API, parses the structured JSON response, and handles
parse failures with a retry. Implement in V2.

---

### Task 3.2 — Add Langfuse tracing
**SKIPPED IN V1**

Wrap every Claude call in a Langfuse `@observe` decorator. Track tokens used, latency,
anomaly metadata, and parse success/failure. Implement in V2.

---

### Task 3.3 — Wire up the real report task
**SKIPPED IN V1**

Replace the V1 mock report task with a full implementation: fetch context, call reporter
service, write to DB, update anomaly status, publish `report_ready` event to Redis.
Implement in V2.

---

### Task 3.4 — Write SSE streaming endpoint
**SKIPPED IN V1**

`GET /api/v1/reports/{anomaly_id}/stream` — streams Claude's response token-by-token
using `StreamingResponse`. Frontend connects via `EventSource`. Implement in V2.

---

### Phase 3 — Complete done-when

> **All Phase 3 done-when conditions are deferred to V2.**
>
> V1 gate (already satisfied by Task 2.6):
> - `USE_MOCK_REPORTS=true` — full pipeline runs, mock reports written to DB with
>   `report_status="completed"`, zero Claude API calls made.

---

## Phase 4 — REST API + WebSocket
**Time estimate: 6–8 hours**
**Goal: Every API contract from api-contracts.md is implemented and tested. WebSocket
broadcasts anomalies within 2 seconds of Redis publish.**

---

### Task 4.1 — Write FastAPI app factory

**What you're doing:** `main.py` sets up the app with lifespan (startup/shutdown),
middleware, and mounts all routers. Nothing business-logic-related goes here.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB connection pool, Redis client
    yield
    # Shutdown: close DB pool, close Redis connections

app = FastAPI(
    title="FinPulse API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_v1_router, prefix="/api/v1")
```

**Done when:** `uvicorn app.main:app --reload` starts. `curl http://localhost:8000/docs`
returns the OpenAPI UI.

---

### Task 4.2 — Implement all REST routes

**What you're doing:** Every route from api-contracts.md, implemented exactly as
specified. No deviations.

Routes to implement:
- `GET /api/v1/stocks/{ticker}/candles` — cursor pagination, query continuous aggregate
- `GET /api/v1/anomalies` — filter by ticker/severity/type/hours, cursor pagination
- `GET /api/v1/reports/{anomaly_id}` — 200/202/404 with correct response schemas
- `GET /api/v1/health` — checks actual DB and Redis connections, returns degraded if either fails

**Critical rules for every route:**
- `response_model=` declared on every route decorator
- Handler body must be under 20 lines — if longer, move logic to a repository
- No `dict` return types anywhere
- 404 returns `{"error": "not_found"}` — not FastAPI's default HTML error page

**Done when:** Every route tested with curl matching the exact response shapes in
api-contracts.md. Health endpoint returns `{"status": "healthy"}` with DB and Redis up.

---

### Task 4.3 — Implement WebSocket with Redis Pub/Sub

**What you're doing:** The WebSocket endpoint that subscribes to Redis and forwards
messages to connected clients. This is the most complex part of Phase 4.

**`api/v1/ws.py`:**

```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Send init payload — last 5 anomalies
    # Client never starts with empty feed
    recent = await anomaly_repo.get_recent(limit=5)
    await websocket.send_json({"type": "init", "data": [a.model_dump() for a in recent]})
    
    # Subscribe to Redis channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("finpulse:anomalies")
    
    # Heartbeat task + message listener running concurrently
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    
    async def listen():
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                validated = AnomalyEventSchema.model_validate(data)
                await websocket.send_json({"type": "anomaly", "data": validated.model_dump()})
    
    try:
        await asyncio.gather(heartbeat(), listen())
    except WebSocketDisconnect:
        await pubsub.unsubscribe("finpulse:anomalies")
        await pubsub.close()
```

**Done when:** Connect via `wscat -c ws://localhost:8000/api/v1/ws`. You receive the init
payload immediately. Then manually publish to Redis:
```bash
redis-cli PUBLISH finpulse:anomalies '{"id":"test","ticker":"TSLA","type":"volume_spike","severity":"HIGH","detected_at":"2026-01-01T00:00:00Z","zscore":4.2}'
```
Message appears in wscat within 2 seconds.

---

### Task 4.4 — Write API integration tests

**What you're doing:** Test every route using `httpx.AsyncClient` with a test database.

**`tests/test_api.py`:**
- `test_get_candles_returns_correct_shape`
- `test_get_anomalies_filters_by_severity`
- `test_get_anomalies_filters_by_ticker`
- `test_get_report_returns_202_when_pending`
- `test_get_report_returns_200_when_completed`
- `test_get_report_returns_404_for_unknown_id`
- `test_health_returns_healthy`

**Done when:** `pytest tests/test_api.py -v` all passing.

---

### Phase 4 — Complete done-when

- [ ] All routes implemented and match api-contracts.md exactly
- [ ] WebSocket sends init payload on connect
- [ ] WebSocket forwards Redis message within 2 seconds
- [ ] `pytest tests/test_api.py -v` — all passing
- [ ] Health endpoint returns degraded when Redis is manually stopped

---

## Phase 5 — Frontend Foundation
**Time estimate: 6–8 hours**
**Goal: React app compiles with zero TypeScript errors. All Zod schemas written. All
TanStack Query hooks written and returning typed data.**

---

### Task 5.1 — Initialize Vite + TypeScript project

**What you're doing:** Create the React app with strict TypeScript, configure path
aliases, install all dependencies.

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query zustand zod axios
npm install @radix-ui/react-* sonner
npm install lightweight-charts
npx shadcn@latest init
```

**Configure path aliases in `vite.config.ts`:**
```typescript
resolve: {
  alias: {
    "@": path.resolve(__dirname, "./src"),
  }
}
```

**Enable strict mode in `tsconfig.json`:**
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  }
}
```

**Done when:** `npm run dev` starts. `tsc --noEmit` passes with zero errors.

---

### Task 5.2 — Write all Zod schemas (first file you write)

**What you're doing:** `lib/schemas.ts` is the first real code file in the frontend.
Every API response shape from api-contracts.md becomes a Zod schema. TypeScript types
are derived — never written by hand.

```typescript
// lib/schemas.ts
import { z } from "zod"

export const CandleSchema = z.object({
  time: z.number(),
  open: z.string(),
  high: z.string(),
  low: z.string(),
  close: z.string(),
  volume: z.number(),
})

export const CandleListResponseSchema = z.object({
  data: z.array(CandleSchema),
  next_cursor: z.string().nullable(),
  has_more: z.boolean(),
  ticker: z.string(),
})

export const SeveritySchema = z.enum(["LOW", "MEDIUM", "HIGH"])
export const AnomalyTypeSchema = z.enum(["volume_spike", "price_swing"])
export const ReportStatusSchema = z.enum(["pending", "completed", "failed"])

export const AnomalySchema = z.object({
  id: z.string().uuid(),
  detected_at: z.string().datetime(),
  candle_time: z.string().datetime(),
  ticker: z.string(),
  type: AnomalyTypeSchema,
  severity: SeveritySchema,
  zscore: z.number().nullable(),
  iqr_flag: z.boolean(),
  report_status: ReportStatusSchema,
})

export const ReportSchema = z.object({
  id: z.string().uuid(),
  anomaly_id: z.string().uuid(),
  summary: z.string(),
  reasons: z.array(z.string()),
  risk_level: z.string(),
  confidence: z.number(),
  tokens_used: z.number(),
  latency_ms: z.number(),
  created_at: z.string().datetime(),
})

// TypeScript types — derived, never written by hand
export type Candle = z.infer<typeof CandleSchema>
export type Anomaly = z.infer<typeof AnomalySchema>
export type Report = z.infer<typeof ReportSchema>
export type Severity = z.infer<typeof SeveritySchema>
```

**Done when:** `tsc --noEmit` passes. Every type used in the frontend can be traced back
to a Zod schema in this file.

---

### Task 5.3 — Write Axios instance with Zod validation interceptor

**What you're doing:** A single Axios instance used everywhere. The response interceptor
runs Zod validation on every API response. If validation fails, it throws a typed error
that TanStack Query catches. This means a backend change that breaks the contract is caught
immediately — not silently producing undefined values.

```typescript
// lib/api.ts
import axios from "axios"
import { ZodSchema } from "zod"

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
})

export async function fetchValidated<T>(
  url: string,
  schema: ZodSchema<T>,
  params?: Record<string, unknown>
): Promise<T> {
  const response = await api.get(url, { params })
  return schema.parse(response.data)  // throws ZodError if shape doesn't match
}
```

**Done when:** A test call to a real endpoint goes through the interceptor. Changing a
field name in the Zod schema causes the call to throw — proving runtime validation works.

---

### Task 5.4 — Write all TanStack Query hooks

**What you're doing:** One hook per API resource. These are the only places `fetchValidated`
is called.

```typescript
// features/chart/useChartData.ts
export function useChartData(ticker: string, hours: number = 24) {
  return useQuery({
    queryKey: ["candles", ticker, hours],
    queryFn: () => fetchValidated(
      `/api/v1/stocks/${ticker}/candles`,
      CandleListResponseSchema,
      { hours }
    ),
    staleTime: 60_000,  // 1 minute — matches ingestion interval
  })
}

// features/anomalies/useAnomalies.ts
export function useAnomalies(ticker?: string, severity?: Severity) {
  return useQuery({
    queryKey: ["anomalies", ticker, severity],
    queryFn: () => fetchValidated(
      "/api/v1/anomalies",
      AnomalyListResponseSchema,
      { ticker, severity, hours: 24 }
    ),
    staleTime: 30_000,
  })
}

// features/reports/useReport.ts
export function useReport(anomalyId: string) {
  return useQuery({
    queryKey: ["report", anomalyId],
    queryFn: () => fetchValidated(
      `/api/v1/reports/${anomalyId}`,
      ReportResponseSchema  // union of completed/pending/failed schemas
    ),
  })
}
```

**Done when:** Each hook called in a test component returns real data from the API.
`tsc --noEmit` passes with zero errors.

---

### Task 5.5 — Write Zustand store

**What you're doing:** UI state only. Selected ticker, open drawer, active filters.
Nothing that comes from the server lives here.

```typescript
// app/store.ts
import { create } from "zustand"

interface UIState {
  selectedTicker: string
  setSelectedTicker: (ticker: string) => void
  openDrawerAnomalyId: string | null
  setOpenDrawer: (anomalyId: string | null) => void
  severityFilter: Severity | null
  setSeverityFilter: (severity: Severity | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  selectedTicker: "TSLA",
  setSelectedTicker: (ticker) => set({ selectedTicker: ticker }),
  openDrawerAnomalyId: null,
  setOpenDrawer: (anomalyId) => set({ openDrawerAnomalyId: anomalyId }),
  severityFilter: null,
  setSeverityFilter: (severity) => set({ severityFilter: severity }),
}))
```

**Done when:** Store imported in a component, state updates trigger re-render. `tsc
--noEmit` passes.

---

### Task 5.6 — Build the TradingView chart component

**What you're doing:** Wrap TradingView Lightweight Charts in a React component.
Candlestick series. Anomaly markers at the correct timestamps. ResizeObserver for
responsive sizing.

```typescript
// features/chart/TradingChart.tsx
import { createChart, CrosshairMode } from "lightweight-charts"

export function TradingChart({ ticker }: { ticker: string }) {
  const chartRef = useRef<HTMLDivElement>(null)
  const { data } = useChartData(ticker)
  
  useEffect(() => {
    if (!chartRef.current || !data) return
    
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      crosshair: { mode: CrosshairMode.Normal },
    })
    
    const candleSeries = chart.addCandlestickSeries()
    candleSeries.setData(data.data.map(c => ({
      time: c.time,
      open: parseFloat(c.open),
      high: parseFloat(c.high),
      low: parseFloat(c.low),
      close: parseFloat(c.close),
    })))
    
    // ResizeObserver for responsive sizing
    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: chartRef.current!.clientWidth })
    })
    observer.observe(chartRef.current)
    
    return () => { chart.remove(); observer.disconnect() }
  }, [data])
  
  return <div ref={chartRef} className="w-full" />
}
```

**Done when:** Chart renders in browser with real candle data. Zoom and pan work.
Resizing the window resizes the chart. Zero TypeScript errors.

---

### Phase 5 — Complete done-when

- [ ] `npm run dev` starts without errors
- [ ] `tsc --noEmit` passes with zero errors — enforced, not optional
- [ ] Chart renders real candlestick data from the API
- [ ] All Zod schemas match the api-contracts.md shapes exactly
- [ ] All TanStack Query hooks return typed data

---

## Phase 6 — Frontend UI
**Time estimate: 6–8 hours**
**Goal: Anomaly list renders and polls for new data every 30 seconds. Clicking an anomaly
opens a report drawer that shows the completed mock report. Zero TypeScript errors.**

> V1 simplifications applied to this phase:
> - WebSocket manager class removed entirely — no `lib/websocket.ts`
> - WebSocket hook removed — replaced with TanStack Query `refetchInterval: 30000`
> - SSE streaming removed from ReportDrawer — report fetched via `GET /api/v1/reports/{id}`, static display
> - TradingView chart not included in the dashboard layout
> - Sonner toast removed — no WebSocket events to trigger it
> - LiveIndicator removed — no connection state to display
> - Watchlist bar simplified to a static TSLA label (no ticker switching in V1)

---

### Task 6.1 — Configure polling on useAnomalies hook

**What you're doing:** In V1, the anomaly feed stays current via TanStack Query's
`refetchInterval`. No WebSocket connection, no custom event handling — just a periodic
REST refetch every 30 seconds.

Update `features/anomalies/useAnomalies.ts` (written in Phase 5) to add `refetchInterval`:

```typescript
export function useAnomalies(ticker?: string, severity?: Severity) {
  return useQuery({
    queryKey: ["anomalies", ticker, severity],
    queryFn: () => fetchValidated(
      "/api/v1/anomalies",
      AnomalyListResponseSchema,
      { ticker, severity, hours: 24 }
    ),
    staleTime: 30_000,
    refetchInterval: 30_000,   // V1: poll every 30 seconds
  })
}
```

**Why refetchInterval instead of WebSocket:** WebSocket requires a persistent server-side
connection, a Redis Pub/Sub subscriber, reconnection logic on the client, and real-time
event handling. For V1, polling every 30 seconds is sufficient — anomalies do not need
to appear in under 30 seconds to be useful. The entire change is one added line.

**Done when:** Browser DevTools network tab shows `GET /api/v1/anomalies` firing every
30 seconds automatically. No WebSocket connection visible in the WS tab.

---

### Task 6.2 — Anomaly feed

**What you're doing:** Scrollable list of anomaly cards. Cards are clickable and open
the report drawer. Feed data comes entirely from the polling hook — no WebSocket, no
manual cache mutations.

**`features/anomalies/AnomalyFeed.tsx`** — key behaviors:
- Uses `useAnomalies()` hook (polling at 30s interval from Task 6.1)
- shadcn `ScrollArea` for the list container
- CSS animation for card entrance (e.g. `animate-in fade-in slide-in-from-top-2`)
- Each card shows: ticker, severity badge, type, time, z-score
- Clicking a card calls `setOpenDrawer(anomaly.id)`

**`features/anomalies/AnomalyCard.tsx`** — displays one anomaly:
- `SeverityBadge` component (red/yellow/blue for HIGH/MEDIUM/LOW)
- Formatted relative time ("2 minutes ago")
- Z-score shown to 2 decimal places
- Subtle border-left color matching severity

**Done when:** Feed shows initial data on page load. After 30 seconds, network tab shows
a refetch and the feed reflects any new anomalies without a page refresh. Zero TypeScript
errors.

---

### Task 6.3 — Report drawer (REST only)

**What you're doing:** A shadcn `Sheet` (side drawer) that opens when an anomaly card
is clicked. Fetches the completed mock report via `GET /api/v1/reports/{anomaly_id}` and
displays the static report text. No SSE, no streaming, no EventSource.

```typescript
// features/reports/ReportDrawer.tsx

export function ReportDrawer() {
  const { openDrawerAnomalyId, setOpenDrawer } = useUIStore()
  const { data, isLoading } = useReport(openDrawerAnomalyId ?? "")

  return (
    <Sheet open={!!openDrawerAnomalyId} onOpenChange={() => setOpenDrawer(null)}>
      <SheetContent>
        {isLoading && (
          <p className="text-muted-foreground">Loading report...</p>
        )}
        {data?.status === "completed" && (
          <div className="space-y-4">
            <p className="text-sm leading-relaxed">{data.report.summary}</p>
            <ul className="list-disc pl-4 space-y-1">
              {data.report.reasons.map((r, i) => (
                <li key={i} className="text-sm text-muted-foreground">{r}</li>
              ))}
            </ul>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Risk: {data.report.risk_level}</span>
              <span>Confidence: {(data.report.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}
        {data?.status === "pending" && (
          <p className="text-muted-foreground">Report is being generated...</p>
        )}
        {data?.status === "failed" && (
          <p className="text-destructive">Report generation failed.</p>
        )}
      </SheetContent>
    </Sheet>
  )
}
```

**Why no SSE:** In V1, `USE_MOCK_REPORTS=true` means the report task writes to the DB
synchronously and immediately marks `report_status = "completed"`. By the time the user
clicks an anomaly card, the report already exists. There is nothing to stream.

**Done when:** Click any anomaly card → drawer opens → report summary and reasons display
immediately. Closing the drawer clears `openDrawerAnomalyId`. No EventSource connection
is created anywhere in the component. Zero TypeScript errors.

---

### Task 6.4 — Dashboard page assembly

**What you're doing:** `pages/Dashboard.tsx` assembles all components into the final
layout. In V1, the TradingView chart is absent — the AnomalyFeed is the primary surface.

**V1 layout:**
```
┌─────────────────────────────────────────────┐
│  FinPulse    TSLA                            │  ← header (static ticker label)
├─────────────────────────────────────────────┤
│                                             │
│   AnomalyFeed (full width)                  │
│   polling every 30 seconds                  │
│                                             │
├─────────────────────────────────────────────┤
│  MetricCard  MetricCard  MetricCard          │  ← summary stats
└─────────────────────────────────────────────┘
```

**MetricCard stats to show:** Total anomalies today, HIGH severity count today,
last ingestion time.

**What is not in the V1 layout:**
- No TradingView chart — the chart column is absent, not commented out
- No LiveIndicator — no WebSocket connection state to show
- No ticker switcher — TSLA is a static label in the header

**Done when:** Full layout renders correctly. AnomalyFeed visible and updating every
30 seconds. MetricCards show real counts from the API. `tsc --noEmit` zero errors.

---

### Phase 6 — Complete done-when

- [ ] `useAnomalies` hook refetches every 30 seconds — confirmed in browser DevTools network tab
- [ ] AnomalyFeed renders anomaly cards from polled data
- [ ] Clicking a card opens ReportDrawer and displays mock report summary + reasons
- [ ] No WebSocket connection present in browser DevTools WS tab
- [ ] No SSE / EventSource connection opened anywhere in the frontend
- [ ] TradingView chart is absent from the layout — not stubbed, not commented out
- [ ] `tsc --noEmit` zero errors — no exceptions, no suppressions

---

## Phase 7 — MCP Server
**SKIPPED IN V1 — Deferred to V2**

> The MCP server gives Claude Desktop natural-language access to live FinPulse data via
> three tools: `get_anomalies`, `get_report`, and `get_market_summary`. In V1, all data
> is already accessible via the REST API. The MCP layer is a convenience for Claude
> Desktop users and is not required for the product to function.
>
> Phase 7 is the full V2 implementation. It covers:
> - MCP server entry point (`mcp_server/server.py`) using the `mcp` Python SDK
> - Three tools with well-engineered descriptions that Claude selects correctly
> - Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`)
> - 10 natural-language query test suite verifying correct tool selection
>
> **Do not implement Phase 7 in V1. The `mcp_server/` folder exists with `.gitkeep` files
> as required by the folder structure — do not add any real code there yet.**

---

### Task 7.1 — Write MCP server entry point
**SKIPPED IN V1**

---

### Task 7.2 — Write the three MCP tools
**SKIPPED IN V1**

---

### Task 7.3 — Configure Claude Desktop and test with 10 queries
**SKIPPED IN V1**

---

### Phase 7 — Complete done-when

> **All Phase 7 done-when conditions are deferred to V2.**

---

## Phase 8 — Tests, Deploy, and Ship
**Time estimate: 6–8 hours**
**Goal: CI is green. Live URL exists. README has GIF and badges. Demo recorded.**

---

### Task 8.1 — Final test pass

**What you're doing:** Run the full test suite and fix anything that's broken. No skipped
tests. No `# type: ignore` comments. No `any` types.

```bash
# All of these must pass
pytest tests/ -v --tb=short           # Backend
cd frontend && tsc --noEmit           # Frontend types
cd frontend && npm run lint           # ESLint
ruff check backend/                   # Python linting
mypy backend/                         # Python types
```

**Target coverage:** All detector functions, all repo methods, all API endpoints.

**Done when:** Every command above exits with code 0. Zero warnings in mypy output.

---

### Task 8.2 — Deploy to Railway

**What you're doing:** Create a Railway project with 4 services (TimescaleDB, Redis,
backend, frontend). Configure environment variables. Run migrations on the live DB.
Verify the health endpoint.

**Steps:**
1. Create Railway project
2. Add TimescaleDB service (Railway has a TimescaleDB template)
3. Add Redis service
4. Deploy backend from GitHub — set `START_COMMAND=uvicorn app.main:app --host 0.0.0.0`
5. Deploy frontend from GitHub — set build command to `npm run build`, serve with Nginx
6. Set all environment variables in Railway dashboard (from .env.example)
7. Run `alembic upgrade head` via Railway shell
8. Run TimescaleDB setup SQL via Railway database shell
9. Keep `USE_MOCK_REPORTS=true` in production for V1

**Done when:** `curl https://your-app.railway.app/api/v1/health` returns
`{"status": "healthy"}`. Live URL is publicly accessible.

---

### Task 8.3 — Record Loom demo

**What you're doing:** 90-second screen recording showing the full product. Do this
during US market hours (7pm–1:30am IST) so you have real anomalies firing.

**Demo script:**
- 0:00–0:15 — Show the dashboard with the TSLA anomaly feed
- 0:15–0:40 — Wait for or trigger an anomaly — show it appearing in the feed after the next poll
- 0:40–1:10 — Click the anomaly card, show the report drawer with summary and reasons
- 1:10–1:30 — Show the health endpoint and DB row counts confirming real data

**Done when:** Loom link exists. Video shows all 4 of the above moments clearly.

---

### Task 8.4 — Write README

**What you're doing:** The README is what a hiring manager sees before looking at any
code. It must answer: what does this do, how is it built, and why should I care.

**Required sections:**
- Live demo badge (link to Railway URL)
- 30-second GIF of the anomaly feed updating
- What it does (1 paragraph, non-technical)
- Architecture diagram (simple ASCII or image)
- Tech stack table with brief why for each choice
- Local setup instructions (`make dev`, then seed script)
- Key engineering decisions (3–4 bullet points, one line each)

**Done when:** A senior engineer could understand what this project does and how it's
built from the README alone, without reading any code.

---

### Phase 8 — Complete done-when

- [ ] All tests passing, zero linting errors, zero TypeScript errors
- [ ] Live Railway URL is publicly accessible
- [ ] Health endpoint returns healthy on live URL
- [ ] Loom demo recorded and linked in README
- [ ] README has GIF, live URL badge, and architecture section
- [ ] ARCHITECTURE.md is complete and matches what you actually built

---

## Master checklist — ship when all of these are green

- [ ] Phase 0: 6 containers start and are healthy with `make dev`
- [ ] Phase 1: Migrations run, hypertable exists, repo tests pass
- [ ] Phase 2: TSLA ingestion fills DB, Z-score detector finds anomalies, 10 unit tests pass, mock reports written to DB with status "completed"
- [ ] Phase 3: **SKIPPED IN V1** — deferred to V2 (Claude API, Langfuse, SSE streaming)
- [ ] Phase 4: All API routes match contracts, WebSocket broadcasts in <2s
- [ ] Phase 5: Zod schemas match contracts, TanStack Query hooks return typed data, `tsc --noEmit` passes
- [ ] Phase 6: Anomaly feed polls every 30s, report drawer shows mock report, zero TypeScript errors, no WebSocket or SSE
- [ ] Phase 7: **SKIPPED IN V1** — deferred to V2 (MCP server, Claude Desktop)
- [ ] Phase 8: Live URL, Loom, README complete

---

*Total estimated time: 44–56 hours across 7–9 days of focused work.*
*Do not rush Phase 0 and Phase 1. Every hour spent there saves three hours in later phases.*
