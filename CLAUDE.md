# CLAUDE.md — FinPulse

This file is the authoritative guide for Claude Code working in this repository.
Read this entire file before touching any code. Every decision here has a reason.
Do not deviate without understanding why the rule exists.

---

## What this project is

FinPulse is a real-time financial market anomaly detection system. It ingests live
OHLCV (Open, High, Low, Close, Volume) market data every 60 seconds, detects
statistically unusual events using Z-score analysis, generates AI-powered research
reports via the Claude API, and surfaces everything through a live React dashboard.

**This is a portfolio project built to production-grade standards.** Every architectural
decision is documented and defensible. Do not simplify or shortcut — the complexity is
intentional and demonstrates engineering maturity.

**What FinPulse is NOT:** It is not a trading system. It does not give buy/sell signals.
It does not manage portfolios. It observes and explains. It does not recommend.

**Current build: V1 scope**
- One ticker only: TSLA
- Z-score anomaly detection only (no IQR in V1)
- Mock reports only (USE_MOCK_REPORTS=true — no real Claude API calls in V1)
- REST polling every 30 seconds (no WebSocket in V1)
- No TradingView chart in V1
- No MCP server in V1

---

## Repository structure

```
finpulse/
├── backend/                          # Python FastAPI application
│   ├── app/
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # pydantic-settings Config — all env vars here
│   │   ├── api/
│   │   │   ├── deps.py               # Shared FastAPI dependencies
│   │   │   └── v1/
│   │   │       ├── router.py         # Mounts all v1 sub-routers
│   │   │       ├── stocks.py
│   │   │       ├── anomalies.py
│   │   │       ├── reports.py
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── database.py           # SQLAlchemy async engine and session factory
│   │   │   └── redis.py              # Redis connection pool
│   │   ├── models/                   # SQLAlchemy ORM models (mapped_column syntax)
│   │   │   ├── base.py
│   │   │   ├── market_data.py
│   │   │   ├── anomaly.py
│   │   │   └── report.py
│   │   ├── schemas/                  # Pydantic v2 request/response schemas
│   │   │   ├── market.py
│   │   │   ├── anomaly.py
│   │   │   └── report.py
│   │   ├── repositories/             # ALL database queries live here and ONLY here
│   │   │   ├── market_repo.py
│   │   │   ├── anomaly_repo.py
│   │   │   └── report_repo.py
│   │   └── services/                 # Business logic — no DB calls inside services
│   │       ├── detector.py           # Pure functions: Z-score anomaly detection
│   │       └── reporter.py           # Mock report generation (Claude API in V2)
│   ├── workers/                      # Celery tasks — separate from API process
│   │   ├── celery_app.py             # Celery app config + Beat schedule
│   │   ├── ingestion_task.py         # Fetches TSLA data from yfinance every 60s
│   │   ├── detection_task.py         # Runs detector, writes anomaly to DB
│   │   └── report_task.py            # Writes mock report to DB
│   ├── migrations/                   # Alembic migration files
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_detector.py
│   │   ├── test_repos.py
│   │   └── test_api.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                         # React 18 + TypeScript
│   ├── src/
│   │   ├── app/
│   │   │   ├── providers.tsx
│   │   │   └── store.ts              # Zustand — UI state only
│   │   ├── pages/
│   │   │   └── Dashboard.tsx
│   │   ├── features/
│   │   │   ├── anomalies/
│   │   │   │   ├── AnomalyFeed.tsx
│   │   │   │   ├── AnomalyCard.tsx
│   │   │   │   └── useAnomalies.ts   # TanStack Query hook with 30s polling
│   │   │   └── reports/
│   │   │       ├── ReportDrawer.tsx
│   │   │       └── useReport.ts
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn components — do not edit
│   │   │   ├── SeverityBadge.tsx
│   │   │   └── MetricCard.tsx
│   │   └── lib/
│   │       ├── schemas.ts            # Zod schemas — single source of truth
│   │       ├── api.ts                # Axios instance + Zod validation interceptor
│   │       └── utils.ts
│   ├── vite.config.ts                # Port 5173
│   ├── tsconfig.json
│   └── Dockerfile
│
├── mcp_server/                       # MCP server (V2 — skip in V1)
│   ├── server.py
│   └── tools/
│
├── infra/
│   ├── docker-compose.yml            # 6 services
│   ├── nginx/
│   │   └── nginx.conf
│   └── db/
│       └── init.sql                  # TimescaleDB extension setup
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── ARCHITECTURE.md
├── CLAUDE.md                         # This file
├── .env.example
└── Makefile
```

---

## Tech stack

### Backend
| Technology | Version | Why |
|---|---|---|
| Python | 3.12 | Latest stable |
| FastAPI | 0.111+ | Async API framework |
| SQLAlchemy | 2.0 async | ORM with mapped_column() syntax |
| TimescaleDB | Latest (PG16) | Time-series DB — hypertables + continuous aggregates |
| Redis | 7+ | Celery broker + Pub/Sub event bus |
| Celery | 5.3+ | Background task queue — separate from API process |
| Pydantic | v2 | Typed schemas for every request/response |
| Alembic | 1.13+ | Schema migrations |
| yfinance | 0.2.38 | Market data fetching |
| Anthropic SDK | Latest | Claude API for reports (V2 only) |
| Langfuse | 2.x | LLM observability (V2 only) |

### Frontend
| Technology | Version | Why |
|---|---|---|
| React | 18 | Concurrent features |
| TypeScript | 5.x | Strict mode, zero any types |
| Vite | 5.x | Fast dev server on port 5173 |
| TanStack Query | v5 | Server state — polls every 30s in V1 |
| Zustand | 4.x | UI state only (selected ticker, open drawer) |
| TailwindCSS + shadcn/ui | Latest | Accessible components |
| Zod | 3.x | Runtime validation + type inference |

### Infrastructure
| Technology | Why |
|---|---|
| Docker + Docker Compose | 6 containerised services |
| Nginx | Reverse proxy for production |
| GitHub Actions | CI: ruff + mypy + pytest + tsc |
| Railway | Production deployment |

---

## The 6 Docker services

| Service | Container | Role |
|---|---|---|
| timescaledb | finpulse_db | Database — stores all data |
| redis | finpulse_redis | Task queue + event bus |
| backend | finpulse_backend | FastAPI API on port 8000 |
| worker | finpulse_worker | Celery worker — executes tasks |
| beat | finpulse_beat | Celery Beat — fires tasks every 60s |
| frontend | finpulse_frontend | React dev server on port 5173 |

---

## Database — 3 tables only

### market_data
One row per OHLCV candle. Composite PK (time, ticker).
This is a TimescaleDB hypertable partitioned by day.

```python
class MarketData(Base):
    time: datetime          # PK with ticker
    ticker: str             # PK with time — "TSLA" in V1
    open: Decimal           # NUMERIC(12,4) — never FLOAT for prices
    high: Decimal           # NUMERIC(12,4)
    low: Decimal            # NUMERIC(12,4)
    close: Decimal          # NUMERIC(12,4)
    volume: int             # BigInteger
```

### anomalies
One row per detected anomaly. Created by the detection worker.

```python
class Anomaly(Base):
    id: UUID
    detected_at: datetime
    candle_time: datetime
    ticker: str
    type: AnomalyType       # "volume_spike" only in V1
    severity: Severity      # LOW | MEDIUM | HIGH
    zscore: float
    iqr_flag: bool          # always False in V1
    report_status: ReportStatus  # pending | completed | failed
```

### reports
One row per AI report. One-to-one with anomaly.

```python
class Report(Base):
    id: UUID
    anomaly_id: UUID        # FK to anomalies.id, unique
    summary: str
    reasons: list           # JSONB array of strings
    risk_level: str
    confidence: float
    tokens_used: int        # 0 in V1 (mock)
    latency_ms: int
    created_at: datetime
```

---

## Non-negotiable rules

### Backend rules

**1. No database calls in services.**
`services/detector.py` and `services/reporter.py` are pure business logic. They receive
data as arguments and return results. They never import or call any repository.

**2. No business logic in repositories.**
Repositories contain SQL queries only. They return rows. They do not decide what the
results mean.

**3. No business logic in route handlers.**
Route handlers validate input, call a repository, and return a response schema. If a
handler is longer than 20 lines it is a code smell.

**4. Every route returns a typed Pydantic response model.**
No route handler returns a raw dict. Every response is declared with `response_model=`.

**5. NUMERIC not FLOAT for all price fields.**
`NUMERIC(12,4)` in DB. `Decimal` in Python. Float arithmetic errors in financial data
are a real production bug. Non-negotiable.

**6. All background work runs in Celery workers.**
Never use `asyncio.create_task()` for ingestion, detection, or report generation.
Celery workers are the correct and only place for this work.

**7. Celery tasks must be idempotent.**
Upsert with `ON CONFLICT DO NOTHING`. Check if a report already exists before generating.
Every task can be safely retried.

**8. Never commit credentials.**
`.env` is in `.gitignore`. All credentials go in `.env` locally and Railway dashboard
in production. `.env.example` documents every key — never a real value.

### Frontend rules

**9. TypeScript types come from Zod only.**
`lib/schemas.ts` is the single source of truth. Types are `z.infer<typeof Schema>`.
Never write a TypeScript interface that duplicates a Zod schema.

**10. Server state in TanStack Query. UI state in Zustand. Never mixed.**
Anomaly list = server state → TanStack Query with `refetchInterval: 30000`.
Selected ticker, open drawer = UI state → Zustand.

**11. No `any` type anywhere.**
If `any` seems necessary, write a Zod schema for that shape instead.

**12. shadcn components live in `components/ui/` and are never modified.**
Extend in a wrapper component in `components/`. Never edit generated shadcn files.

**13. Every API response is Zod-validated before use.**
The axios interceptor in `lib/api.ts` runs Zod parse on every response. Do not bypass
this by calling `axios.get()` directly — always use the `api` instance.

---

## Data flow — V1

### Every 60 seconds
```
Beat
→ drops ingest_market_data task into Redis queue
→ Worker picks up task
→ yfinance.download(["TSLA"], interval="1m", period="1d")
→ parse DataFrame (columns are (field, ticker) — NOT (ticker, field))
→ filter: only candles newer than last_ingested_time
→ drop NaN volume rows
→ upsert into market_data (ON CONFLICT (time, ticker) DO NOTHING)
→ chain: detect_anomalies.si("TSLA")
```

### Detection (chained after ingestion)
```
Worker
→ query rolling stats from market_data (last 20 candles)
→ get latest candle
→ zscore = (current_volume - mean) / std
→ if zscore < 2.5: no anomaly, stop
→ if zscore 2.5–3.5: severity = MEDIUM
→ if zscore > 3.5: severity = HIGH
→ write anomaly to DB (report_status = "pending")
→ chain: generate_report.si(anomaly_id)
```

### Report generation — V1 mock
```
Worker
→ check if report already exists (idempotency)
→ USE_MOCK_REPORTS=true: return hardcoded ReportSchema immediately
→ write to reports table
→ update anomaly.report_status = "completed"
```

### Frontend — V1 polling
```
React (TanStack Query, every 30 seconds)
→ GET /api/v1/anomalies
→ Backend queries anomalies table
→ Returns JSON
→ Zod validates response
→ AnomalyFeed re-renders with new cards

User clicks anomaly card
→ GET /api/v1/reports/{anomaly_id}
→ Backend queries reports table
→ Returns completed report JSON
→ ReportDrawer renders summary + reasons
```

---

## Anomaly detection logic — V1

Only Z-score. No IQR in V1.

```python
# Rolling stats from last 20 candles
mean_volume = avg(last_20_candles.volume)
std_volume  = stddev(last_20_candles.volume)

# Z-score on current candle
zscore = (current_volume - mean_volume) / std_volume

# Severity — V1 (Z-score only)
if zscore > 3.5:   severity = HIGH
if zscore > 2.5:   severity = MEDIUM
if zscore <= 2.5:  no anomaly
```

Minimum candles required before detection runs: 20.
If fewer than 20 candles exist in DB for TSLA, skip detection entirely.

**V2 additions (do not implement in V1):**
- IQR price swing detection
- Two-signal severity matrix
- WebSocket broadcast after anomaly creation
- Real Claude API report generation
- Langfuse tracing

---

## API contracts

### GET /api/v1/stocks/{ticker}/candles
Query: `interval=1m|5m|15m`, `hours=1-168`, `cursor?`
```json
{
  "data": [{"time": 1713000000, "open": "182.50", "high": "183.10",
             "low": "182.20", "close": "182.90", "volume": 1250000}],
  "next_cursor": "ISO8601|null",
  "has_more": true,
  "ticker": "TSLA"
}
```

### GET /api/v1/anomalies
Query: `ticker?`, `severity?`, `type?`, `hours=1-168`, `cursor?`
```json
{
  "data": [{
    "id": "uuid",
    "detected_at": "ISO8601",
    "candle_time": "ISO8601",
    "ticker": "TSLA",
    "type": "volume_spike",
    "severity": "HIGH",
    "zscore": 4.23,
    "iqr_flag": false,
    "report_status": "completed"
  }],
  "next_cursor": "uuid|null",
  "has_more": false
}
```

### GET /api/v1/reports/{anomaly_id}
```json
// 200 completed
{"id": "uuid", "anomaly_id": "uuid", "summary": "string",
 "reasons": ["string"], "risk_level": "High",
 "confidence": 0.91, "tokens_used": 0, "latency_ms": 12,
 "created_at": "ISO8601"}

// 202 pending
{"status": "pending", "estimated_ready_at": "ISO8601"}

// 200 failed
{"status": "failed", "error": "generation_failed"}

// 404
{"error": "report_not_found"}
```

### GET /api/v1/health
```json
{"status": "healthy", "db": "ok", "redis": "ok",
 "last_ingestion": "ISO8601", "anomalies_24h": 3}
```

---

## Environment variables

All variables defined in `backend/app/config.py` using pydantic-settings.
App fails loudly on startup if any required variable is missing.

```
# Database (TimescaleDB)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finpulse
DB_USER=postgres
DB_PASSWORD=

# Redis
REDIS_URL=redis://localhost:6379/0

# AI (V2 only — stub values fine for V1)
ANTHROPIC_API_KEY=sk-ant-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# App
TICKERS=TSLA
ANOMALY_ZSCORE_THRESHOLD=2.5
USE_MOCK_REPORTS=true
BACKEND_URL=http://localhost:8000

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/api/v1/ws
```

---

## TimescaleDB specifics

**Alembic does not handle hypertables or continuous aggregates.**
Alembic manages regular DDL only. After running migrations, these must be run manually:

```sql
-- Convert market_data to hypertable (run once after first migration)
SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');

-- In V1, rolling stats are computed from raw rows (no continuous aggregate yet)
-- V2 adds: CREATE MATERIALIZED VIEW market_data_stats WITH (timescaledb.continuous)
```

**Use NUMERIC(12,4) for all price columns.**
SQLAlchemy type: `Numeric(12, 4)`. Python type: `Decimal`.
Floats introduce rounding errors in financial calculations. Non-negotiable.

**After seeding historical data, refresh manually:**
```sql
-- V2 only (after continuous aggregate exists)
CALL refresh_continuous_aggregate('market_data_stats', NULL, NULL);
```

---

## Common commands

```bash
make dev            # Start all 6 Docker services (detached)
make down           # Stop all services
make logs           # Tail all service logs
make build          # Build all Docker images

make migrate        # alembic upgrade head
make migration      # alembic revision --autogenerate -m "description"
make db             # Open psql in TimescaleDB container
make redis-cli      # Open redis-cli in Redis container

make test           # pytest + tsc --noEmit
make lint           # ruff + mypy + tsc --noEmit
make shell          # Python shell in backend container
```

---

## Failure modes

| What fails | Defined behaviour |
|---|---|
| yfinance unavailable | Celery retries 3x (30s, 60s, 120s backoff). Dashboard shows stale data — no crash. |
| Detection with < 20 candles | Skip silently. Log a debug message. Do not write a failed anomaly. |
| Report task fails | Set anomaly.report_status = "failed". Frontend shows "Report unavailable". Never a blank screen. |
| TimescaleDB slow query | Log warning if query exceeds 500ms. |

---

## Testing expectations

### Must be tested
- All `services/detector.py` functions — minimum 8 test cases:
  normal data, clear spike, borderline below threshold, borderline above threshold,
  fewer than 20 candles (should skip), all identical volumes (std=0, no divide by zero),
  extreme outlier, HIGH vs MEDIUM boundary
- All repository methods — against a real test database, not mocks
- API endpoints — using `httpx.AsyncClient` with test database

### Does not need tests (V1)
- Celery task wiring (tested via service + repo unit tests)
- MCP server (V2)

### Running tests
```bash
make test                              # all tests
pytest tests/test_detector.py -v      # detector unit tests only
pytest tests/ -v -s                   # with print output
cd frontend && tsc --noEmit           # frontend types only
```

---

## What this demonstrates to hiring managers

1. **Celery + Redis for background work** — process isolation, API never blocks
2. **TimescaleDB** — time-series thinking, not just "I used Postgres"
3. **Repository pattern** — DB logic in one layer, services are pure business logic
4. **Zod as single source of truth** — type drift prevention at API boundary
5. **Statistical anomaly detection** — Z-score with mathematical reasoning
6. **Defined failure modes** — every component has documented behaviour when it fails

Be ready to explain every decision above out loud in an interview.
The ARCHITECTURE.md file has full reasoning for each choice.
