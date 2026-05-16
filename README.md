# FinPulse

> Real-time financial market anomaly detection with AI-powered analysis reports.

![Demo](docs/demo.gif)

[![CI](https://github.com/SAMEER-SRIVASTAVA/finpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/SAMEER-SRIVASTAVA/finpulse/actions)
[![Live](https://img.shields.io/badge/live-railway-blueviolet)](https://finpulse.up.railway.app)

---

## What it does

FinPulse watches TSLA stock data in real time. Every 60 seconds it ingests the latest 1-minute OHLCV candle from Yahoo Finance, runs a Z-score statistical test against a rolling 20-candle baseline, and flags any volume that deviates by more than 2.5 standard deviations as an anomaly. When an anomaly is found, an AI report is generated explaining the event — what happened, why it might be significant, and the estimated risk level. Everything is surfaced through a live dashboard that refreshes automatically every 30 seconds.

It does not give trading advice. It observes and explains.

---

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │           Docker Compose             │
                         │                                      │
  yfinance API ──────────►  Celery Beat  (fires every 60s)     │
                         │       │                              │
                         │       ▼                              │
                         │  Celery Worker  ──► TimescaleDB      │
                         │  (ingestion)         market_data     │
                         │       │                              │
                         │       ▼                              │
                         │  Celery Worker  ──► TimescaleDB      │
                         │  (Z-score detect)    anomalies       │
                         │       │                              │
                         │       ▼                              │
                         │  Celery Worker  ──► TimescaleDB      │
                         │  (mock report)       reports         │
                         │                                      │
                         │  FastAPI  ◄────── React Dashboard    │
                         │  (REST API)       (30s polling)      │
                         │                                      │
                         └─────────────────────────────────────┘
```

Six isolated services. The API never blocks on background work. Workers fail without affecting the dashboard.

---

## Tech stack

### Backend
| Technology | Why |
|---|---|
| **FastAPI** | Async Python API with automatic OpenAPI docs and typed response models |
| **TimescaleDB** (PostgreSQL) | Hypertable partitioning makes time-range queries milliseconds instead of seconds at scale |
| **Celery + Redis** | Worker processes are fully isolated from the API — a crashed worker doesn't take down the dashboard |
| **SQLAlchemy 2.0 async** | `mapped_column()` syntax with full type inference, async session management |
| **Pydantic v2** | Strict request/response validation with zero-cost `from_attributes` ORM bridging |
| **Alembic** | Schema migrations tracked in version control; hypertable setup handled separately in `init.sql` |
| **yfinance** | Market data source for 1-minute OHLCV candles |
| **NUMERIC(12,4)** | All prices stored as exact decimals — floats introduce rounding errors in financial data |

### Frontend
| Technology | Why |
|---|---|
| **React 18 + TypeScript (strict)** | Concurrent rendering, zero `any` types enforced by compiler |
| **TanStack Query v5** | Server state with built-in polling, caching, deduplication — no manual loading flags |
| **Zustand** | UI-only state (drawer open/closed, selected anomaly) kept strictly separate from server state |
| **Zod** | Every API response is runtime-validated before it reaches a component — schema drift surfaces immediately |
| **Tailwind CSS** | Dark terminal palette with custom severity colour tokens |

### Infrastructure
| Technology | Why |
|---|---|
| **Docker Compose** | All 6 services start with one command, health checks enforce correct startup order |
| **GitHub Actions** | 4-job CI: ruff (lint) → mypy (types) → pytest (tests) → tsc + eslint (frontend) |
| **Railway** | Single-command production deployment with managed TimescaleDB and Redis |

---

## How it works — the detection pipeline

```
1. Beat fires ingest_market_data every 60 seconds
2. Worker fetches TSLA 1m candle from yfinance
3. ON CONFLICT DO NOTHING upsert into market_data (idempotent)
4. If new rows inserted → chain detect_anomalies

5. Worker queries rolling mean and std of last 20 candles
6. zscore = (current_volume − mean) / std
7. zscore ≤ 2.5  → no anomaly, stop
8. zscore > 2.5  → MEDIUM severity
9. zscore > 3.5  → HIGH severity
10. Write Anomaly row (report_status = pending)
11. Chain generate_report

12. Worker generates report (mock in V1, Claude API in V2)
13. Write Report row, set report_status = completed

14. React dashboard polls GET /api/v1/anomalies every 30s
15. User clicks card → GET /api/v1/reports/{id} → drawer opens
```

---

## Local setup

### Prerequisites
- Docker Desktop
- `make`

### Run

```bash
git clone https://github.com/SAMEER-SRIVASTAVA/finpulse.git
cd finpulse

# Copy environment config
cp .env.example .env
# Edit .env — at minimum set DB_PASSWORD

# Start all 6 services
make dev

# Run database migrations (first time only)
make migrate

# Open psql and convert market_data to a TimescaleDB hypertable (first time only)
make db
# Inside psql:
# SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');
# \q

# Dashboard is now live at http://localhost:5173
```

> Data starts appearing after the first 60-second ingestion cycle. During US market hours (9:30am–4:00pm ET) you'll see real TSLA candles. Outside market hours, the feed shows historical data already in the DB.

### Seed historical data (optional)

To populate the DB with past data immediately rather than waiting for live ingestion:

```bash
make shell
# Inside the Python shell:
# import asyncio
# from backend.seed import seed
# asyncio.run(seed())
```

### Run tests

```bash
make test          # pytest + tsc --noEmit
make lint          # ruff + mypy + tsc + eslint
```

---

## Key engineering decisions

**Celery over asyncio.create_task()** — Workers run in separate processes. A worker that OOMs or segfaults on a bad candle batch leaves the API completely unaffected. asyncio background tasks die with the request that created them.

**TimescaleDB over plain Postgres** — With 1-minute candles across multiple tickers, you accumulate ~1.5M rows/year. Time-chunk partitioning means "last 20 candles" touches one chunk, not the full table. At 10M rows, this is the difference between 5ms and 5s.

**Zod at the API boundary** — TypeScript types are erased at runtime. Zod is not. Every API response is parsed against a schema before it enters the React render cycle. If a backend field is renamed, the app throws a typed error immediately in development — not a silent undefined in production.

**Repository pattern with pure services** — Repositories contain SQL and nothing else. Services contain business logic and nothing else (no DB imports). This makes the Z-score detector fully unit-testable with zero infrastructure: `pytest tests/test_detector.py` runs in milliseconds with no database, no Docker, no network.

---

## Project structure

```
finpulse/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routes (anomalies, reports, stocks, health)
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── repositories/    # All DB queries — one layer, no exceptions
│   │   ├── schemas/         # Pydantic v2 request/response schemas
│   │   └── services/        # Pure business logic (detector, reporter)
│   ├── workers/             # Celery tasks (ingestion, detection, report)
│   ├── migrations/          # Alembic schema migrations
│   └── tests/               # pytest (37 tests — unit + integration)
├── frontend/
│   └── src/
│       ├── features/        # anomalies/ and reports/ feature modules
│       ├── lib/             # schemas.ts (Zod), api.ts (Axios), utils.ts
│       └── app/             # Zustand store, React providers
├── infra/
│   └── docker-compose.yml   # 6 services with health checks
├── .github/workflows/ci.yml # 4-job CI pipeline
└── ARCHITECTURE.md          # Full reasoning for every tech decision
```

---

## V1 scope

V1 is a fully working, deployable product. V2 adds:
- Real Claude API reports with Langfuse tracing (replacing mock)
- WebSocket push from Redis Pub/Sub (replacing 30s polling)
- IQR price-swing detection as a second signal
- TradingView candlestick chart with anomaly markers
- MCP server for Claude Desktop integration

---

## API

```
GET /api/v1/health                    → system status
GET /api/v1/stocks/{ticker}/candles   → paginated OHLCV candles
GET /api/v1/anomalies                 → paginated anomaly list (filter by severity/ticker)
GET /api/v1/reports/{anomaly_id}      → 200 completed | 202 pending | 404 not found
```

Full contract: [`api-contracts.md`](api-contracts.md)
