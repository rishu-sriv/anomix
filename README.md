```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║    ███████╗██╗███╗   ██╗██████╗ ██╗   ██╗██╗     ███████╗███████╗          ║
║    ██╔════╝██║████╗  ██║██╔══██╗██║   ██║██║     ██╔════╝██╔════╝          ║
║    █████╗  ██║██╔██╗ ██║██████╔╝██║   ██║██║     ███████╗█████╗            ║
║    ██╔══╝  ██║██║╚██╗██║██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝            ║
║    ██║     ██║██║ ╚████║██║     ╚██████╔╝███████╗███████║███████╗          ║
║    ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝          ║
║                                                                              ║
║          ⚡  Real-Time Market Anomaly Detection + AI Analysis  ⚡            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

<div align="center">

[![CI](https://github.com/SAMEER-SRIVASTAVA/finpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/SAMEER-SRIVASTAVA/finpulse/actions)
[![Live](https://img.shields.io/badge/🚀%20LIVE-Railway-7c3aed?style=for-the-badge)](https://finpulse.up.railway.app)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-PG16-FDB515?style=for-the-badge&logo=postgresql&logoColor=black)

</div>

---

```
  MARKET FEED  ──────────────────────────────────────────────  LIVE  ●
  ┌─────────────────────────────────────────────────────────────────┐
  │  TSLA   $182.90  ▲ +2.3%    VOL: 1,250,000                     │
  │                                                                 │
  │         │                         ┃                            │
  │         │  ┃        ┃             ┃                            │
  │    ┃    ┃  ┃   ┃    ┃    ┃        ┃   ← ANOMALY DETECTED      │
  │    ┃    ┃  ┃   ┃    ┃    ┃   ┃    ┃       Z-SCORE: 4.23       │
  │  ──┸────┸──┸───┸────┸────┸───┸────┸──────── SEVERITY: HIGH ── │
  │   09:30 09:31 09:32 09:33 09:34 09:35 09:36 09:37  >>>        │
  └─────────────────────────────────────────────────────────────────┘
```

> **FinPulse** watches TSLA in real time. Every 60 seconds it ingests a fresh
> 1-minute OHLCV candle, runs a Z-score test against a rolling 20-candle baseline,
> and fires an AI-generated report the moment something statistically unusual happens.
>
> **It does not give trading advice. It observes and explains.**

---

## 📈 What Just Happened?

```
  ┌──── ANOMALY REPORT ─────────────────────────────────────────────────┐
  │                                                                      │
  │  🔴  HIGH SEVERITY   TSLA   Volume Spike   Z-Score: 4.23            │
  │                                                                      │
  │  "Unusual volume surge detected at 09:37 ET. Current volume         │
  │  of 1.25M shares is 4.2 standard deviations above the 20-          │
  │  candle rolling mean of 287,000. This level of activity             │
  │  typically precedes or follows a significant catalyst..."           │
  │                                                                      │
  │  Risk Level: HIGH   Confidence: 91%   Generated: <1s                │
  │                                                                      │
  │  Possible reasons:                                                   │
  │    ▸ Institutional accumulation or distribution event               │
  │    ▸ News-driven retail momentum                                     │
  │    ▸ Options expiry-related volume cluster                          │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture — The Engine Room

```
                    ╔══════════════════════════════════════════╗
                    ║         6 Docker Services                ║
                    ╠══════════════════════════════════════════╣
                    ║                                          ║
  Yahoo Finance ───►║  ⏱  Celery Beat  (every 60s)           ║
                    ║          │                               ║
                    ║          ▼                               ║
                    ║  🔧 Worker: Ingest  ──►  📊 TimescaleDB ║
                    ║          │               market_data     ║
                    ║          ▼                               ║
                    ║  🔧 Worker: Z-Score ──►  🚨 TimescaleDB ║
                    ║     Detect Anomaly        anomalies      ║
                    ║          │                               ║
                    ║          ▼                               ║
                    ║  🔧 Worker: AI Report ►  📝 TimescaleDB ║
                    ║     (Mock V1 / Claude V2)  reports       ║
                    ║                                          ║
                    ║  ⚡ FastAPI  ◄──────  🖥  React Dash    ║
                    ║   REST API            30s polling        ║
                    ║                                          ║
                    ╚══════════════════════════════════════════╝
```

> The API process **never blocks** on background work. A worker that crashes on a bad candle
> leaves the dashboard completely unaffected.

---

## 🧮 The Detection Algorithm

```
  ROLLING WINDOW (last 20 candles)
  ─────────────────────────────────────────────────────────────────
  
  μ  =  avg(volume₁ … volume₂₀)          ← rolling mean
  σ  =  stddev(volume₁ … volume₂₀)       ← rolling std deviation
  
  Z  =  ( Vₙₒw  −  μ )  ÷  σ            ← how many σ from normal?
  
  ─────────────────────────────────────────────────────────────────
  
        Z ≤ 2.5   →   ✅  NORMAL          no action
   2.5 < Z ≤ 3.5  →   🟡  MEDIUM          alert + report
        Z > 3.5   →   🔴  HIGH            alert + urgent report
  
  ─────────────────────────────────────────────────────────────────
  Minimum 20 candles required. If DB has fewer → skip silently.
```

---

## ⚙️ Tech Stack

### 🐍 Backend

| Layer | Technology | The Trade-off Won |
|:---:|---|---|
| 🌐 API | **FastAPI 0.111** | Async-native, auto OpenAPI docs, typed response models |
| 🗄️ Database | **TimescaleDB (PG16)** | Hypertable chunking — "last 20 candles" hits one chunk, not 1.5M rows |
| ⚙️ Workers | **Celery + Redis 7** | Process isolation — worker OOM ≠ API crash |
| 🔗 ORM | **SQLAlchemy 2.0 async** | `mapped_column()` syntax + async sessions |
| ✅ Validation | **Pydantic v2** | Zero-cost ORM bridging, strict request/response contracts |
| 💲 Precision | **NUMERIC(12,4)** | Floats introduce rounding errors in prices. Non-negotiable. |
| 📦 Migrations | **Alembic** | Schema changes version-controlled alongside code |
| 📡 Data | **yfinance 0.2.38** | 1-minute OHLCV candles for TSLA |

### ⚛️ Frontend

| Layer | Technology | The Trade-off Won |
|:---:|---|---|
| 🖼️ UI | **React 18 + TypeScript (strict)** | Concurrent rendering, zero `any` enforced by compiler |
| 🔄 Server State | **TanStack Query v5** | Built-in polling, caching, deduplication — no manual loading flags |
| 🗂️ UI State | **Zustand 4** | Drawer open/closed lives here. Server data never touches Zustand. |
| 🛡️ Runtime Safety | **Zod 3** | Every API response is schema-validated before it reaches a component |
| 🎨 Styling | **Tailwind + shadcn/ui** | Dark terminal palette, accessible primitives |

### 🏗️ Infrastructure

| | Technology | The Trade-off Won |
|:---:|---|---|
| 📦 Containers | **Docker Compose** | All 6 services start with `make dev`, health checks enforce startup order |
| 🔁 CI | **GitHub Actions** | `ruff → mypy → pytest → tsc + eslint` — all 4 gates must pass |
| 🚀 Deploy | **Railway** | Managed TimescaleDB + Redis, one-command deploy |

---

## 🚀 Get Running in 3 Minutes

### Prerequisites
```
  ✓  Docker Desktop
  ✓  make
  ✓  That's it.
```

### Fire it up

```bash
# Clone
git clone https://github.com/SAMEER-SRIVASTAVA/finpulse.git
cd finpulse

# Configure
cp .env.example .env
# Edit .env — set DB_PASSWORD at minimum

# Launch all 6 services
make dev

# First-time DB setup
make migrate

make db
# In psql ↓
# SELECT create_hypertable('market_data', 'time', chunk_time_interval => INTERVAL '1 day');
# \q

# ✅  Dashboard live at http://localhost:5173
```

```
  ⏱  Data starts flowing after the first 60-second ingestion cycle.
  🕘  During US market hours (9:30am–4:00pm ET) you'll see live TSLA candles.
  📦  Outside hours — historical data already in the DB is served.
```

### Optional: Seed historical data

```bash
make shell
# asyncio.run(seed())   ← populates DB immediately without waiting for live feed
```

### Tests

```bash
make test       # pytest + tsc --noEmit
make lint       # ruff + mypy + tsc + eslint
```

---

## 🔌 API Endpoints

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  GET  /api/v1/health                                                │
  │       → { status, db, redis, last_ingestion, anomalies_24h }       │
  │                                                                     │
  │  GET  /api/v1/stocks/{ticker}/candles?interval=1m&hours=1          │
  │       → paginated OHLCV candles                                     │
  │                                                                     │
  │  GET  /api/v1/anomalies?severity=HIGH&hours=24                     │
  │       → paginated anomaly list with Z-scores and severity           │
  │                                                                     │
  │  GET  /api/v1/reports/{anomaly_id}                                  │
  │       → 200 completed  |  202 pending  |  404 not found            │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
finpulse/
├── 🐍 backend/
│   ├── app/
│   │   ├── api/v1/          ← FastAPI routes (anomalies, reports, stocks, health)
│   │   ├── models/          ← SQLAlchemy ORM models
│   │   ├── repositories/    ← ALL DB queries live here — nowhere else
│   │   ├── schemas/         ← Pydantic v2 request/response schemas
│   │   └── services/        ← Pure business logic (detector, reporter)
│   ├── workers/             ← Celery tasks (ingest → detect → report)
│   ├── migrations/          ← Alembic schema versions
│   └── tests/               ← pytest (unit + integration, real DB)
│
├── ⚛️  frontend/
│   └── src/
│       ├── features/        ← anomalies/ and reports/ feature modules
│       ├── lib/             ← schemas.ts (Zod), api.ts (Axios+Zod), utils.ts
│       └── app/             ← Zustand store, React providers
│
├── 🏗️  infra/
│   └── docker-compose.yml   ← 6 services with health checks
│
└── ⚙️  .github/workflows/   ← 4-job CI pipeline
```

---

## 🧠 Key Engineering Decisions

```
  ┌── Why NOT asyncio.create_task()? ───────────────────────────────────┐
  │  Celery workers are separate OS processes. A worker that OOMs on    │
  │  a bad candle batch leaves the API completely alive. asyncio tasks  │
  │  die with the request that spawned them.                            │
  └──────────────────────────────────────────────────────────────────────┘

  ┌── Why TimescaleDB over plain Postgres? ─────────────────────────────┐
  │  1-minute candles = ~1.5M rows/year. Time-chunk partitioning means  │
  │  "last 20 candles" touches ONE chunk, not the full table.           │
  │  At 10M rows this is the difference between 5ms and 5s.             │
  └──────────────────────────────────────────────────────────────────────┘

  ┌── Why Zod at the API boundary? ─────────────────────────────────────┐
  │  TypeScript types are erased at runtime. Zod is not. Every API      │
  │  response is parsed before entering React. A renamed backend field  │
  │  throws a typed error immediately in dev — not a silent             │
  │  `undefined` discovered in production.                              │
  └──────────────────────────────────────────────────────────────────────┘

  ┌── Why Repository pattern + pure services? ──────────────────────────┐
  │  Repositories = SQL only. Services = logic only (no DB imports).    │
  │  The Z-score detector is fully unit-testable in milliseconds with   │
  │  zero infrastructure — no database, no Docker, no network.          │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Failure Modes — Nothing Breaks Silently

| What fails | Defined behavior |
|:---:|---|
| 🌐 yfinance down | Celery retries 3× (30s → 60s → 120s backoff). Dashboard shows stale data. No crash. |
| 📉 < 20 candles | Detection skips silently. Debug log written. No failed anomaly row created. |
| 🤖 Report fails | `anomaly.report_status = "failed"`. Frontend shows "Report unavailable". No blank screen. |
| 🐢 Slow DB query | Warning logged if query exceeds 500ms. |

---

## 🗺️ Roadmap

```
  V1  ████████████████████████████  ✅ SHIPPED
      TSLA · Z-score detection · Mock AI reports · REST polling

  V2  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  PLANNED
      ▸ Real Claude API reports with Langfuse tracing
      ▸ WebSocket push from Redis Pub/Sub (replaces 30s polling)
      ▸ IQR price-swing detection as a second signal
      ▸ TradingView candlestick chart with anomaly markers
      ▸ MCP server for Claude Desktop integration
```

---

<div align="center">

```
  ▲ TSLA    ▲ ARCHITECTURE.md    ▲ API contracts
  Built with obsessive precision. Every decision is documented and defensible.
```

**[Architecture deep-dive →](ARCHITECTURE.md)**

</div>
