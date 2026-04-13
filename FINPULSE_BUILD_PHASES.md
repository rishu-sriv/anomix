# FinPulse — Granular Build Phase Breakdown

> Read this before touching any code. Every task has a clear input, output, and done-when
> condition. Never move to the next task until the current one is verifiably complete.
> "It works on my machine" is not done. The done-when condition is done.

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
**Goal: Data flows from yfinance into TimescaleDB. Anomalies are detected and written to
DB. The full detection pipeline works end-to-end without the API.**

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

**What you're doing:** The task that fires every 60 seconds. Fetches data from yfinance
for all configured tickers in a single batch call, parses the MultiIndex DataFrame
correctly, filters to new candles only, and upserts into TimescaleDB.

**`workers/ingestion_task.py`:**

Key implementation details:
- Single `yf.download()` call for ALL tickers at once — not one call per ticker
- MultiIndex parsing: columns are `(field, ticker)` — access as `df["Close"]["TSLA"]`
- Track last ingestion time per ticker in Redis to filter out already-seen candles
- Drop rows where volume is NaN (yfinance returns NaN for incomplete candles)
- Drop rows where OHLC are all identical (these are stale/duplicated rows yfinance sometimes returns)
- Upsert with `ON CONFLICT (time, ticker) DO NOTHING` — never plain INSERT
- Market hours guard: skip task entirely outside 9:30am–4:00pm ET Monday–Friday
- After successful upsert: chain `detect_anomalies.si(ticker)` for each ticker with new data

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
market_data`. Rows should be present. Running it a second time should not increase the
count (idempotency check).

---

### Task 2.3 — Write the detector service (pure functions)

**What you're doing:** The core anomaly detection logic. Pure functions — no database
calls, no side effects. Takes data as arguments, returns results. This is the most
important business logic in the entire project.

**`services/detector.py`:**

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class RollingStats:
    avg_volume: float
    std_volume: float
    avg_price_change: float
    std_price_change: float
    q1_price_change: float
    q3_price_change: float

@dataclass
class DetectionResult:
    is_anomaly: bool
    anomaly_type: Optional[str]   # "volume_spike" | "price_swing"
    severity: Optional[str]       # "LOW" | "MEDIUM" | "HIGH"
    zscore: Optional[float]
    iqr_flag: bool

def detect_volume_zscore(current_volume: int, stats: RollingStats) -> tuple[float, bool]:
    """
    Returns (zscore, is_above_threshold).
    zscore = (current - mean) / std
    Threshold: 2.5 standard deviations above mean.
    """
    if stats.std_volume == 0:
        return 0.0, False
    zscore = (current_volume - stats.avg_volume) / stats.std_volume
    return zscore, zscore > ZSCORE_THRESHOLD

def detect_price_swing_iqr(price_change_pct: float, stats: RollingStats) -> bool:
    """
    Returns True if price_change is an IQR outlier.
    Outlier = outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
    """
    iqr = stats.q3_price_change - stats.q1_price_change
    lower_fence = stats.q1_price_change - (1.5 * iqr)
    upper_fence = stats.q3_price_change + (1.5 * iqr)
    return price_change_pct < lower_fence or price_change_pct > upper_fence

def determine_severity(zscore: float, iqr_flag: bool) -> Optional[str]:
    """
    Severity matrix:
    zscore > 3.5 AND iqr_flag  → HIGH
    zscore > 3.5               → MEDIUM
    zscore > 2.5 AND iqr_flag  → MEDIUM
    zscore > 2.5               → LOW
    iqr_flag only              → LOW
    neither                    → None (no anomaly)
    """
    if zscore > 3.5 and iqr_flag:
        return "HIGH"
    elif zscore > 3.5:
        return "MEDIUM"
    elif zscore > 2.5 and iqr_flag:
        return "MEDIUM"
    elif zscore > 2.5:
        return "LOW"
    elif iqr_flag:
        return "LOW"
    return None

def run_detection(candle: dict, stats: RollingStats) -> DetectionResult:
    """
    Main entry point. Takes one candle + rolling stats, returns DetectionResult.
    """
    price_change = float((candle["close"] - candle["open"]) / candle["open"] * 100)
    zscore, volume_spike = detect_volume_zscore(candle["volume"], stats)
    iqr_flag = detect_price_swing_iqr(price_change, stats)
    severity = determine_severity(zscore, iqr_flag)
    
    return DetectionResult(
        is_anomaly=severity is not None,
        anomaly_type="volume_spike" if volume_spike else ("price_swing" if iqr_flag else None),
        severity=severity,
        zscore=zscore,
        iqr_flag=iqr_flag
    )
```

**Why pure functions:** Services have no side effects — they receive data and return
results. The Celery task handles all DB reads/writes around the service call. This means
the detection logic can be unit tested with zero database, zero mocking, zero infrastructure.

**Done when:** `python -c "from app.services.detector import run_detection"` imports
without error. No database imports anywhere in the file.

---

### Task 2.4 — Write detector unit tests

**What you're doing:** At least 8 unit tests covering every edge case. These tests run
in milliseconds — no database, no network, no Docker required. Just Python.

**`tests/test_detector.py`** — required test cases:

```
test_no_anomaly_on_normal_data
    Input: volume at exactly the mean, price change in normal range
    Expected: DetectionResult(is_anomaly=False)

test_volume_spike_detected_above_threshold
    Input: volume = mean + (3 * std)  # clearly above 2.5 threshold
    Expected: is_anomaly=True, anomaly_type="volume_spike"

test_borderline_volume_just_below_threshold
    Input: volume = mean + (2.4 * std)  # just below 2.5
    Expected: is_anomaly=False

test_borderline_volume_just_above_threshold
    Input: volume = mean + (2.6 * std)  # just above 2.5
    Expected: is_anomaly=True

test_empty_candle_list_raises_or_returns_none
    Input: stats with std_volume=0 (no variance in data)
    Expected: zscore=0.0, no anomaly (division by zero handled)

test_single_candle_no_historical_data
    Input: stats with avg=current volume (zscore would be 0)
    Expected: no anomaly

test_all_identical_volumes
    Input: std_volume=0 (flat line)
    Expected: no anomaly, no ZeroDivisionError

test_extreme_outlier_scores_high_severity
    Input: volume = mean + (5 * std), price change outside IQR fences
    Expected: severity="HIGH", iqr_flag=True

test_iqr_only_anomaly_scores_low
    Input: volume below zscore threshold, price change outside IQR fences
    Expected: severity="LOW", anomaly_type="price_swing"

test_severity_matrix_high_requires_both_signals
    Input: zscore=4.0, iqr_flag=False
    Expected: severity="MEDIUM" (not HIGH — needs both)
```

**Done when:** `pytest tests/test_detector.py -v` shows 10+ tests passing. Zero database
connections made during this test run.

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

**Done when:** Seed 2 weeks of historical data, run `CALL
refresh_continuous_aggregate('market_data_stats', NULL, NULL)` in psql, then trigger
detection manually. Check the anomalies table. You should see 2–8 anomalies per ticker
per week. If you see hundreds, your threshold is too low. If you see zero, your continuous
aggregate hasn't refreshed — run the manual refresh call.

---

### Task 2.6 — Write the report task (stub only)

**What you're doing:** Write the report task skeleton so the detection task chain doesn't
fail. The real implementation is Phase 3. For now it just logs the anomaly_id and returns.

```python
@app.task
async def generate_report(anomaly_id: str):
    logger.info(f"Report generation stub called for {anomaly_id}")
    # Real implementation in Phase 3
```

**Done when:** Full pipeline runs without errors — ingestion → detection → report stub.
No task failures in Celery logs.

---

### Phase 2 — Complete done-when

- [ ] `celery -A workers.celery_app worker` starts and connects to Redis
- [ ] Manual ingestion task call inserts rows into market_data
- [ ] Second call doesn't insert duplicates (idempotency)
- [ ] `pytest tests/test_detector.py -v` — 10+ tests passing, zero DB connections
- [ ] Full chain: ingestion → detection → report stub — runs without errors
- [ ] 2–8 anomalies per ticker visible in DB after seeding + detection run

---

## Phase 3 — AI Report Generation
**Time estimate: 6–8 hours**
**Goal: Anomalies trigger Claude (or mock) report generation. Reports are structured JSON
stored in DB. Langfuse traces every call.**

---

### Task 3.1 — Write the reporter service

**What you're doing:** The service that builds prompts, calls Claude, parses the
structured JSON response, and handles failures. Pure business logic — no DB calls.

**`services/reporter.py`:**

**System prompt (engineer this carefully):**
```
You are a financial market analyst. You will be given data about an unusual market event.
Your job is to provide a factual, data-driven explanation of what the data shows.

Rules:
- Reference only the specific numbers provided. Do not speculate about future price moves.
- Do not give buy/sell recommendations.
- Respond ONLY with valid JSON. No preamble, no explanation, no markdown.
- The JSON must match this exact schema: {"summary": string, "reasons": [string], "risk_level": "Low"|"Medium"|"High", "confidence": float 0-1}
```

**User prompt template:**
```python
def build_prompt(anomaly: Anomaly, candles: list, stats: RollingStats) -> str:
    return f"""
Market anomaly detected for {anomaly.ticker} at {anomaly.candle_time.isoformat()}.

Anomaly type: {anomaly.type.value}
Severity: {anomaly.severity.value}
Z-score: {anomaly.zscore:.2f} (volume was {anomaly.zscore:.1f} standard deviations above the 20-period mean)

Current candle:
- Volume: {candles[0].volume:,} shares
- Price move: {((candles[0].close - candles[0].open) / candles[0].open * 100):.2f}% intraday
- Open: ${candles[0].open}, Close: ${candles[0].close}

Rolling statistics (last 20 periods):
- Average volume: {stats.avg_volume:,.0f} shares
- Volume std dev: {stats.std_volume:,.0f} shares
- Normal price change range: {stats.q1_price_change:.2f}% to {stats.q3_price_change:.2f}%

Respond with JSON only.
"""
```

**Parse + retry logic:**
```python
async def generate_report(anomaly, candles, stats) -> ReportSchema:
    if settings.use_mock_reports:
        return mock_report()
    
    prompt = build_prompt(anomaly, candles, stats)
    
    # Attempt 1
    raw = await call_claude(prompt)
    try:
        return ReportSchema.model_validate_json(raw)
    except ValidationError:
        logger.warning("First parse failed, retrying with stricter prompt")
    
    # Attempt 2 — stricter prompt
    strict_prompt = prompt + "\n\nCRITICAL: Your last response was not valid JSON. Respond with ONLY the JSON object, nothing else."
    raw2 = await call_claude(strict_prompt)
    try:
        return ReportSchema.model_validate_json(raw2)
    except ValidationError:
        # Log both to Langfuse, raise to mark task as failed
        log_failed_attempts(anomaly.id, prompt, raw, strict_prompt, raw2)
        raise ReportGenerationError("Both parse attempts failed")
```

**Done when:** `USE_MOCK_REPORTS=true` — calling `generate_report()` returns a valid
`ReportSchema` without any network calls. `USE_MOCK_REPORTS=false` with a valid
`ANTHROPIC_API_KEY` — real Claude response is parsed and returned.

---

### Task 3.2 — Add Langfuse tracing

**What you're doing:** Wrap every Claude call in a Langfuse trace. Track: tokens used,
latency, anomaly metadata (ticker, severity), whether parse succeeded or failed.

```python
from langfuse import Langfuse
from langfuse.decorators import observe

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host
)

@observe(name="generate_anomaly_report")
async def call_claude(prompt: str, anomaly_metadata: dict) -> str:
    start = time.time()
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = int((time.time() - start) * 1000)
    
    # Langfuse automatically captures via @observe decorator
    # Add custom metadata
    langfuse.trace(
        metadata={
            "ticker": anomaly_metadata["ticker"],
            "severity": anomaly_metadata["severity"],
            "latency_ms": latency_ms,
            "tokens": response.usage.input_tokens + response.usage.output_tokens
        }
    )
    
    return response.content[0].text
```

**Done when:** Trigger a real Claude call (USE_MOCK_REPORTS=false). Open Langfuse
dashboard. Trace is visible with correct token count and latency. This proves observability
is working before you ship to production.

---

### Task 3.3 — Wire up the real report task

**What you're doing:** Replace the Phase 2 stub with the real implementation. The task
fetches all context, calls the reporter service, writes to DB, updates anomaly status,
publishes to Redis.

**`workers/report_task.py` full implementation:**

```python
@app.task(bind=True, max_retries=1)
async def generate_report(self, anomaly_id: str):
    async with get_db_session() as session:
        # Fetch context
        anomaly = await anomaly_repo.get_by_id(uuid.UUID(anomaly_id), session)
        if anomaly is None:
            logger.error(f"Anomaly {anomaly_id} not found")
            return
        
        # Check if report already exists (idempotency)
        existing = await report_repo.get_by_anomaly_id(anomaly.id, session)
        if existing is not None:
            logger.info(f"Report already exists for {anomaly_id}, skipping")
            return
        
        candles, _ = await market_repo.get_candles(anomaly.ticker, hours=1, limit=10, session=session)
        stats = await market_repo.get_rolling_stats(anomaly.ticker, session)
        
        try:
            report_data = await reporter.generate_report(anomaly, candles, stats)
            
            # Write to DB
            report = await report_repo.create(ReportCreate(
                anomaly_id=anomaly.id,
                **report_data.model_dump(),
            ), session)
            
            # Update anomaly status
            await anomaly_repo.update_report_status(anomaly.id, ReportStatus.completed, session)
            
            # Notify frontend via Redis
            await redis_client.publish(
                f"report_ready:{anomaly_id}",
                json.dumps({"anomaly_id": anomaly_id})
            )
            
        except ReportGenerationError:
            await anomaly_repo.update_report_status(anomaly.id, ReportStatus.failed, session)
```

**Done when:** Trigger detect_anomalies manually for a ticker with seeded data. Check
reports table — a row should exist with valid JSON in the `reasons` column. Check anomalies
table — `report_status` should be "completed".

---

### Task 3.4 — Write SSE streaming endpoint

**What you're doing:** An endpoint that streams Claude's response token-by-token as it
generates. The frontend connects via `EventSource` and shows text appearing in real time.

**`api/v1/reports.py`** — SSE endpoint:

```python
@router.get("/reports/{anomaly_id}/stream")
async def stream_report(anomaly_id: uuid.UUID):
    async def event_generator():
        async with anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'token': text})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Done when:** `curl -N http://localhost:8000/api/v1/reports/{id}/stream` shows tokens
arriving one by one in the terminal. `[DONE]` appears at the end.

---

### Phase 3 — Complete done-when

- [ ] `USE_MOCK_REPORTS=true` — full pipeline runs, reports written to DB, zero Claude API calls
- [ ] `USE_MOCK_REPORTS=false` — real Claude response parsed and stored
- [ ] Langfuse dashboard shows traces with token counts and latency
- [ ] Both parse-fail paths tested: first attempt fails → retry → second fails → status="failed"
- [ ] SSE stream endpoint returns tokens progressively
- [ ] `pytest tests/test_detector.py tests/test_repos.py -v` — all still passing

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
**Goal: React app renders real candlestick data with anomaly markers. TypeScript compiles
with zero errors. All API hooks written.**

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
**Time estimate: 8–10 hours**
**Goal: Full end-to-end user experience. Anomaly detected → card appears in feed →
click → streaming report drawer. Zero TypeScript errors.**

---

### Task 6.1 — WebSocket manager class

**What you're doing:** A singleton class that manages the WebSocket connection,
reconnection logic, and event dispatching. This is custom code — no library handles
this exact pattern for you.

```typescript
// lib/websocket.ts
type WSEventHandler = (data: unknown) => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers: Map<string, WSEventHandler[]> = new Map()
  private reconnectDelay = 1000
  private maxDelay = 30000
  
  connect(url: string) {
    this.ws = new WebSocket(url)
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      const handlers = this.handlers.get(message.type) ?? []
      handlers.forEach(h => h(message.data))
    }
    
    this.ws.onclose = () => {
      // Exponential backoff reconnection
      setTimeout(() => {
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
        this.connect(url)
      }, this.reconnectDelay)
    }
    
    this.ws.onopen = () => {
      this.reconnectDelay = 1000  // reset on successful connection
    }
  }
  
  on(type: string, handler: WSEventHandler) {
    const existing = this.handlers.get(type) ?? []
    this.handlers.set(type, [...existing, handler])
  }
  
  off(type: string, handler: WSEventHandler) {
    const existing = this.handlers.get(type) ?? []
    this.handlers.set(type, existing.filter(h => h !== handler))
  }
}

// Singleton — one instance for the entire app
export const wsManager = new WebSocketManager()
```

**Done when:** `wsManager.connect(url)` establishes connection. Manually closing the
connection in Chrome DevTools → reconnects after 1 second. Closing again → 2 seconds.
Again → 4 seconds.

---

### Task 6.2 — React WebSocket hook

**What you're doing:** A hook that connects the WebSocket manager to TanStack Query
cache. New anomaly events update the query cache directly — no refetch needed.

```typescript
// lib/websocket.ts (hook)
export function useWebSocket() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<"connected"|"reconnecting"|"disconnected">("disconnected")
  
  useEffect(() => {
    wsManager.connect(import.meta.env.VITE_WS_URL)
    
    const handleAnomaly = (data: unknown) => {
      const anomaly = AnomalySchema.parse(data)
      
      // Update cache directly — no network request
      queryClient.setQueryData(["anomalies"], (old: AnomalyListResponse | undefined) => ({
        ...old,
        data: [anomaly, ...(old?.data ?? [])].slice(0, 50)  // keep last 50
      }))
      
      // Toast for HIGH severity
      if (anomaly.severity === "HIGH") {
        toast.error(`HIGH severity anomaly: ${anomaly.ticker} ${anomaly.type}`)
      }
    }
    
    wsManager.on("anomaly", handleAnomaly)
    return () => wsManager.off("anomaly", handleAnomaly)
  }, [queryClient])
  
  return { status }
}
```

**Done when:** Keep the browser open. Manually trigger detection from the terminal.
Anomaly card appears in the frontend feed within 2 seconds WITHOUT a page refresh.

---

### Task 6.3 — Anomaly feed with animation

**What you're doing:** scrollable list of anomaly cards. New cards animate in from the
top. Cards are clickable and open the report drawer.

**`features/anomalies/AnomalyFeed.tsx`** — key behaviors:
- Uses `useAnomalies()` hook for initial data
- `useWebSocket()` hook keeps cache updated in real time
- shadcn `ScrollArea` for the list container
- `framer-motion` or CSS animation for card entrance
- Each card shows: ticker, severity badge, type, time, z-score
- Clicking a card calls `setOpenDrawer(anomaly.id)`

**`features/anomalies/AnomalyCard.tsx`** — displays one anomaly:
- `SeverityBadge` component (red/yellow/blue for HIGH/MEDIUM/LOW)
- Formatted relative time ("2 minutes ago")
- Z-score shown to 2 decimal places
- Subtle border-left color matching severity

**Done when:** Feed shows initial data on load. New anomaly triggered manually appears
at top of feed with animation within 2 seconds. HIGH severity fires a toast notification.

---

### Task 6.4 — Report drawer with SSE streaming

**What you're doing:** A shadcn `Sheet` (side drawer) that opens when a card is clicked.
Fetches the report — if pending, opens SSE connection and streams tokens as Claude generates.

```typescript
// features/reports/ReportDrawer.tsx

export function ReportDrawer() {
  const { openDrawerAnomalyId, setOpenDrawer } = useUIStore()
  const [streamedText, setStreamedText] = useState("")
  
  useEffect(() => {
    if (!openDrawerAnomalyId) return
    
    const es = new EventSource(
      `${import.meta.env.VITE_API_BASE_URL}/api/v1/reports/${openDrawerAnomalyId}/stream`
    )
    
    es.onmessage = (event) => {
      if (event.data === "[DONE]") { es.close(); return }
      const { token } = JSON.parse(event.data)
      setStreamedText(prev => prev + token)
    }
    
    es.onerror = () => es.close()
    
    return () => es.close()
  }, [openDrawerAnomalyId])
  
  return (
    <Sheet open={!!openDrawerAnomalyId} onOpenChange={() => setOpenDrawer(null)}>
      <SheetContent>
        <div className="prose">{streamedText || "Generating report..."}</div>
      </SheetContent>
    </Sheet>
  )
}
```

**Done when:** Click anomaly card → drawer opens → text appears character by character
as Claude generates. If report is already completed, full text appears immediately.
Closing drawer stops the SSE connection.

---

### Task 6.5 — Connection status indicator + watchlist bar

**`components/LiveIndicator.tsx`:** Pulsing green dot when WebSocket is connected.
Yellow pulsing when reconnecting. Red when disconnected. Shows the string "Live" /
"Reconnecting..." / "Disconnected" next to the dot.

**`features/watchlist/WatchlistBar.tsx`:** Row of ticker buttons at the top. Each shows
the ticker name and a badge with the count of HIGH severity anomalies in the last 24h.
Clicking a ticker updates `selectedTicker` in Zustand store, which updates the chart
and anomaly feed.

**Done when:** Disconnect from WiFi → indicator shows "Reconnecting..." → reconnect →
shows "Live" again. Clicking a ticker changes the chart data.

---

### Task 6.6 — Dashboard page assembly

**What you're doing:** `pages/Dashboard.tsx` assembles all components into the final
layout. Two-column layout: chart + watchlist on the left, anomaly feed on the right.

**Layout structure:**
```
┌─────────────────────────────────────────────┐
│  FinPulse    [TSLA] [NVDA] [AAPL]   ● Live  │  ← header
├─────────────────────┬───────────────────────┤
│                     │                       │
│   TradingChart      │   AnomalyFeed         │
│   (60% width)       │   (40% width)         │
│                     │                       │
├─────────────────────┴───────────────────────┤
│  MetricCard  MetricCard  MetricCard          │  ← summary stats
└─────────────────────────────────────────────┘
```

**MetricCard stats to show:** Total anomalies today, HIGH severity count today,
last ingestion time.

**Done when:** Full layout renders correctly. All components visible. Responsive on
different screen sizes. `tsc --noEmit` zero errors.

---

### Phase 6 — Complete done-when

- [ ] Full end-to-end flow: anomaly detected → card appears → click → streaming report
- [ ] WebSocket reconnects automatically with exponential backoff
- [ ] HIGH severity fires sonner toast
- [ ] `tsc --noEmit` zero errors — no exceptions, no suppressions
- [ ] LiveIndicator shows correct connection state
- [ ] Watchlist ticker switching updates chart and feed

---

## Phase 7 — MCP Server
**Time estimate: 4–5 hours**
**Goal: Claude Desktop can query live FinPulse data using natural language.**

---

### Task 7.1 — Write MCP server entry point

**What you're doing:** A separate Python process that exposes three tools to Claude
Desktop. No shared code with the backend — communicates only via REST API.

```python
# mcp_server/server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("finpulse")

# Register tools
from mcp_server.tools.anomalies import get_anomalies
from mcp_server.tools.reports import get_report
from mcp_server.tools.market import get_market_summary

server.add_tool(get_anomalies)
server.add_tool(get_report)
server.add_tool(get_market_summary)

if __name__ == "__main__":
    stdio_server(server)
```

**Done when:** `python mcp_server/server.py` starts without errors.

---

### Task 7.2 — Write the three MCP tools

**What you're doing:** Each tool is a function with a description, input schema, and
implementation that calls the REST API. The description is the most important part.

**Tool 1 — get_anomalies:**
```python
description = """
Retrieves detected market anomalies for a specific stock ticker or across all monitored
tickers. Use when the user asks about unusual market activity, volume spikes, abnormal
price movements, or market alerts for any stock. Returns anomaly type (volume_spike or
price_swing), severity level (LOW/MEDIUM/HIGH), Z-score value, and timestamp of detection.

Examples:
- "What anomalies happened in TSLA today?"
- "Show me HIGH severity alerts from the last hour"
- "Any unusual activity in NVDA?"
"""
```

**Tool 2 — get_report:**
```python
description = """
Retrieves the AI-generated analysis report for a specific anomaly. Use when the user
wants to understand WHY an anomaly occurred or wants more detail about a specific alert.
Requires an anomaly_id which can be obtained from get_anomalies. Returns a summary,
list of reasons, risk level, and confidence score.
"""
```

**Tool 3 — get_market_summary:**
```python
description = """
Returns a summary of market activity across all monitored tickers for a given time
period. Use when the user asks for an overview of market conditions, which stocks have
been most active, or a general summary of anomaly activity. Returns anomaly counts
per ticker, most recent anomaly per ticker, and overall activity level.
"""
```

**Done when:** Each tool correctly calls the REST API and returns structured data.
Test with `python -c "from mcp_server.tools.anomalies import get_anomalies"`.

---

### Task 7.3 — Configure Claude Desktop and test with 10 queries

**What you're doing:** Add the MCP server to Claude Desktop config. Test with 10 real
natural language queries to verify tools are invoked correctly.

**Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "finpulse": {
      "command": "python",
      "args": ["/absolute/path/to/finpulse/mcp_server/server.py"],
      "env": {
        "BACKEND_URL": "http://localhost:8000"
      }
    }
  }
}
```

**10 test queries:**
1. "What anomalies happened in TSLA in the last 24 hours?"
2. "Show me all HIGH severity alerts today"
3. "Any unusual activity in NVDA?"
4. "Give me a summary of market activity today"
5. "What was the Z-score for the last TSLA anomaly?"
6. "Get the report for the most recent anomaly"
7. "Which ticker had the most anomalies today?"
8. "Were there any volume spikes in AAPL this week?"
9. "What's the confidence score on the latest report?"
10. "Compare anomaly activity between TSLA and NVDA today"

**Done when:** All 10 queries return real data from your running system. Claude correctly
selects the right tool for each query without being told which tool to use.

---

### Phase 7 — Complete done-when

- [ ] MCP server starts without errors
- [ ] All 3 tools have descriptions that would make sense to a new engineer reading them
- [ ] All 10 test queries in Claude Desktop return real live data
- [ ] Claude selects correct tools without explicit instruction

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
9. Set `USE_MOCK_REPORTS=false` in production

**Done when:** `curl https://your-app.railway.app/api/v1/health` returns
`{"status": "healthy"}`. Live URL is publicly accessible.

---

### Task 8.3 — Record Loom demo

**What you're doing:** 90-second screen recording showing the full product. Do this
during US market hours (7pm–1:30am IST) so you have real anomalies firing.

**Demo script:**
- 0:00–0:15 — Show the dashboard with real tickers and live chart
- 0:15–0:40 — Wait for or trigger an anomaly — show it appearing in the feed
- 0:40–1:00 — Click the anomaly card, show the streaming report generating in real time
- 1:00–1:20 — Switch to Claude Desktop, ask "What anomalies happened in TSLA today?"
- 1:20–1:30 — Show the health endpoint and Langfuse dashboard briefly

**Done when:** Loom link exists. Video shows all 4 of the above moments clearly.

---

### Task 8.4 — Write README

**What you're doing:** The README is what a hiring manager sees before looking at any
code. It must answer: what does this do, how is it built, and why should I care.

**Required sections:**
- Live demo badge (link to Railway URL)
- 30-second GIF of the real-time feed updating
- What it does (1 paragraph, non-technical)
- Architecture diagram (simple ASCII or image)
- Tech stack table with brief why for each choice
- Local setup instructions (`make dev`, then seed script)
- Key engineering decisions (3–4 bullet points, one line each)
- Langfuse observability screenshot

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
- [ ] Phase 2: Ingestion fills DB, detector finds 2–8 anomalies/ticker/week, 10 unit tests pass
- [ ] Phase 3: Reports generated (mock + real), Langfuse traces visible
- [ ] Phase 4: All API routes match contracts, WebSocket broadcasts in <2s
- [ ] Phase 5: Chart renders real data, zero TypeScript errors
- [ ] Phase 6: Full end-to-end flow working, reconnection works
- [ ] Phase 7: 10 Claude Desktop queries return real data
- [ ] Phase 8: Live URL, Loom, README complete

---

*Total estimated time: 52–68 hours across 8–10 days of focused work.*
*Do not rush Phase 0 and Phase 1. Every hour spent there saves three hours in later phases.*
