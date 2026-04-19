# Phase 0 — Foundation
## Complete Implementation Plan

> This is not a high-level overview. This is line-by-line, file-by-file, command-by-command.
> Follow in order. Do not skip steps. Do not move to Phase 1 until every done-when is green.

**What Phase 0 produces:** A running skeleton with 6 healthy Docker containers, a passing
CI pipeline, and a Makefile that controls everything. Zero features. Zero business logic.
Just infrastructure that proves the system can run.

**Why this matters:** Every phase after this builds on top of this foundation. A broken
Docker Compose setup will cost you 4 hours in Phase 2. A broken CI pipeline will cost you
a day when you're ready to deploy. Spend the time now.

**Estimated time:** 4–6 hours

---

## Prerequisites — install these before starting

```bash
# Verify each of these works before you touch any project code

docker --version          # Docker 24+ required
docker compose version    # Docker Compose v2 required (note: no hyphen)
git --version             # Git 2.x
node --version            # Node 20+
npm --version             # npm 9+
python3 --version         # Python 3.12
make --version            # GNU Make (pre-installed on Mac/Linux)
```

If any of these fail, install them first. Do not proceed without all 6 working.

**On Mac:** Install Docker Desktop. It includes Docker Compose v2.
**On Ubuntu:** `sudo apt install docker.io docker-compose-plugin make`

---

## Step 1 — Create the GitHub repository

Do this first. Everything else is committed as you build it.

1. Go to github.com → New repository
2. Name: `finpulse`
3. Visibility: **Public** (hiring managers need to see it)
4. Initialize with README: **Yes**
5. .gitignore template: **Python**
6. Clone to your machine:

```bash
git clone https://github.com/YOUR_USERNAME/finpulse.git
cd finpulse
```

**Done when:** `git status` inside the finpulse directory shows a clean working tree.

---

## Step 2 — Create the full folder structure

Run this entire block as one command from inside the `finpulse/` directory.
This creates every folder the project needs. Do it all at once — not incrementally.

```bash
# Backend
mkdir -p backend/app/api/v1
mkdir -p backend/app/core
mkdir -p backend/app/models
mkdir -p backend/app/schemas
mkdir -p backend/app/repositories
mkdir -p backend/app/services
mkdir -p backend/workers
mkdir -p backend/migrations/versions
mkdir -p backend/tests

# Frontend
mkdir -p frontend/src/app
mkdir -p frontend/src/pages
mkdir -p frontend/src/features/chart
mkdir -p frontend/src/features/anomalies
mkdir -p frontend/src/features/reports
mkdir -p frontend/src/features/watchlist
mkdir -p frontend/src/components/ui
mkdir -p frontend/src/lib

# MCP Server
mkdir -p mcp_server/tools

# Infrastructure
mkdir -p infra/nginx
mkdir -p infra/db

# CI
mkdir -p .github/workflows
```

Add `.gitkeep` files so empty folders are tracked by Git:

```bash
find . -type d -empty -not -path "./.git/*" -exec touch {}/.gitkeep \;
```

Verify the structure:

```bash
find . -type d | grep -v node_modules | grep -v .git | sort
```

**Done when:** Output shows all 34 folders. No extra folders, no missing ones.

---

## Step 3 — Write ARCHITECTURE.md

Create this file at the project root. Write it in your own words.
This is not documentation for users — it's documentation for interviewers and your future self.

```bash
touch ARCHITECTURE.md
```

**Required content — write one section per decision:**

```markdown
# FinPulse — Architecture Decisions

## 1. Celery + Redis for background work (not asyncio)

**Decision:** All ingestion, detection, and report generation runs as Celery tasks in
separate worker processes. The FastAPI application never runs heavy work inline.

**Why:** If ingestion crashes inside the API process, the API dies. Celery workers are
completely isolated — the API stays alive even when a worker fails. Celery also gives
us retries, exponential backoff, task state visibility, and the ability to scale workers
horizontally without touching the API. asyncio.create_task() inside a route handler is
a shortcut that creates a single point of failure.

## 2. TimescaleDB over plain PostgreSQL

**Decision:** market_data is a TimescaleDB hypertable partitioned by day. Rolling stats
are precomputed in a continuous aggregate view (market_data_stats).

**Why:** A query for "last 20 candles for TSLA" on a plain Postgres table with 10M rows
scans all rows and takes seconds. On a hypertable, it only touches the relevant time
chunk — milliseconds. Continuous aggregates precompute rolling mean/std/percentiles so
the detector never scans raw rows at all. Querying raw market_data for stats defeats the
entire purpose of TimescaleDB.

## 3. Redis Pub/Sub as event bus between workers and WebSocket handlers

**Decision:** When the detection worker finds an anomaly, it publishes to a Redis channel.
The FastAPI WebSocket handler subscribes to that channel and forwards to connected clients.

**Why:** A Celery worker has no knowledge of which WebSocket connections exist on which
API instance. If we have 3 API instances running, a direct call would only reach one.
Redis decouples workers from API instances — worker publishes once, every subscribed API
instance receives it and forwards to its clients. This is what makes the system
horizontally scalable without any coordination logic.

## 4. TanStack Query for server state, Zustand for UI state only

**Decision:** All API data lives in TanStack Query cache. Only purely local UI state
(selected ticker, open drawer, active filter) lives in Zustand.

**Why:** Server state is fundamentally different from client state. It's async, can be
stale, needs background refetching, can fail, and needs cache invalidation. Putting server
state in Zustand requires manually handling all of this. TanStack Query handles it by
design. Mixing them creates stale data bugs that are hard to trace.

## 5. Zod as single source of truth for TypeScript types

**Decision:** Every TypeScript type is derived from a Zod schema via z.infer<>. No
TypeScript interfaces are written by hand. Zod validates every API response at runtime.

**Why:** If we write Pydantic schemas in Python AND TypeScript interfaces by hand, they
will drift when someone changes a field. With Zod, the schema IS the type — if the
backend changes a field name, Zod throws a runtime error on the next API call immediately,
before the broken value reaches any component. TypeScript alone can't do this because
types are erased at runtime.

## 6. Two-signal anomaly detection (Z-score AND IQR)

**Decision:** A HIGH severity anomaly requires BOTH Z-score > 3.5 AND IQR flag. Either
signal alone produces MEDIUM or LOW.

**Why:** Z-score is sensitive to previous outliers in the window. If there was a massive
spike 15 candles ago, it inflates the rolling mean and compresses future Z-scores —
making the detector blind to real anomalies. IQR (interquartile range) uses percentiles
which are outlier-resistant. When both fire together, it's strong evidence of a real event
rather than a statistical artifact. One signal alone fires too often on noise.
```

**Done when:** File exists with all 6 sections written. If you can't write the reasoning
for any section in your own words, go back and re-read the relevant section of CLAUDE.md.
This file will be read by interviewers.

---

## Step 4 — Write api-contracts.md

```bash
touch api-contracts.md
```

Full content to write:

```markdown
# FinPulse — API Contracts

These contracts are locked. Frontend and backend implement against this document.
If a contract changes, update this file, the Zod schema, the Pydantic schema,
and any affected tests — all in the same commit.

---

## Base URL

Development: http://localhost:8000/api/v1
Production:  https://your-app.railway.app/api/v1

---

## Pagination

All list endpoints use cursor pagination.
- Pass `cursor` query param to get the next page
- Response includes `next_cursor` (null if no more pages) and `has_more` boolean
- Default page size: 20 items

---

## Error responses

All errors follow this shape:
{ "error": "error_code_string" }

Common error codes:
- ticker_not_found
- report_not_found
- invalid_cursor
- validation_error

---

## GET /stocks/{ticker}/candles

Query parameters:
- interval: "1m" | "5m" | "15m"  (default: "1m")
- hours: integer 1-168            (default: 24)
- cursor: string (optional)

Response 200:
{
  "data": [
    {
      "time": 1713000000,       // Unix timestamp (integer)
      "open": "182.50",         // String decimal — never float
      "high": "183.10",
      "low": "182.20",
      "close": "182.90",
      "volume": 1250000
    }
  ],
  "next_cursor": "2026-04-12T14:32:00Z",  // null if no more pages
  "has_more": true,
  "ticker": "TSLA"
}

Response 404:
{ "error": "ticker_not_found" }

---

## GET /anomalies

Query parameters:
- ticker: string (optional)
- severity: "LOW" | "MEDIUM" | "HIGH" (optional)
- type: "volume_spike" | "price_swing" (optional)
- hours: integer 1-168 (default: 24)
- cursor: string (optional)

Response 200:
{
  "data": [
    {
      "id": "uuid",
      "detected_at": "2026-04-12T14:32:00Z",  // ISO8601
      "candle_time": "2026-04-12T14:31:00Z",
      "ticker": "TSLA",
      "type": "volume_spike",
      "severity": "HIGH",
      "zscore": 4.23,
      "iqr_flag": true,
      "report_status": "completed"   // "pending" | "completed" | "failed"
    }
  ],
  "next_cursor": "uuid-string",
  "has_more": false
}

---

## GET /reports/{anomaly_id}

Response 200 (completed):
{
  "id": "uuid",
  "anomaly_id": "uuid",
  "summary": "TSLA experienced an unusual volume spike...",
  "reasons": [
    "Volume was 4.2x above the 20-period mean",
    "Z-score of 4.23 exceeds HIGH threshold of 3.5"
  ],
  "risk_level": "High",
  "confidence": 0.87,
  "tokens_used": 312,
  "latency_ms": 1420,
  "created_at": "2026-04-12T14:32:05Z"
}

Response 202 (pending — report still generating):
{
  "status": "pending",
  "estimated_ready_at": "2026-04-12T14:32:10Z"
}

Response 200 (failed — generation failed):
{
  "status": "failed",
  "error": "generation_failed"
}

Response 404:
{ "error": "report_not_found" }

---

## GET /health

Response 200 (healthy):
{
  "status": "healthy",
  "db": "ok",
  "redis": "ok",
  "last_ingestion": "2026-04-12T14:31:00Z",
  "anomalies_24h": 12
}

Response 200 (degraded — never return 5xx for health checks):
{
  "status": "degraded",
  "db": "ok",
  "redis": "timeout",
  "last_ingestion": "2026-04-12T14:31:00Z",
  "anomalies_24h": 12
}

---

## WebSocket /ws

Connect: ws://localhost:8000/api/v1/ws

Message types (server → client):

On connect — last 5 anomalies as init payload:
{ "type": "init", "data": [ /* array of anomaly objects */ ] }

New anomaly detected:
{ "type": "anomaly", "data": { "id": "uuid", "ticker": "TSLA", "type": "volume_spike", "severity": "HIGH", "detected_at": "ISO8601", "zscore": 4.23, "iqr_flag": true } }

Report finished generating:
{ "type": "report_ready", "data": { "anomaly_id": "uuid" } }

Heartbeat (every 30s — client should respond or connection may be dropped):
{ "type": "ping" }
```

**Done when:** Every route exists in this file with request shape, all response shapes
including error cases, and example values. No endpoint should be left as "TBD".

---

## Step 5 — Write .env.example

```bash
touch .env.example
```

```bash
# ============================================================
# FinPulse Environment Variables
# Copy this file to .env and fill in real values.
# NEVER commit .env to Git. It is in .gitignore.
# ============================================================

# --- Database ---
# TimescaleDB connection details
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finpulse
DB_USER=postgres
DB_PASSWORD=change_me_in_production

# --- Redis ---
# Used as both Celery broker and Pub/Sub event bus
REDIS_URL=redis://localhost:6379/0

# --- AI ---
# Get from console.anthropic.com
# Set a spend limit on your account before adding this
ANTHROPIC_API_KEY=sk-ant-api03-...

# --- LLM Observability ---
# Get from cloud.langfuse.com (free tier is sufficient)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# --- App Config ---
# Comma-separated list of stock tickers to monitor
# Add BTC-USD, ETH-USD for 24/7 testing outside market hours
TICKERS=AAPL,TSLA,NVDA,MSFT,GOOGL,BTC-USD

# Z-score threshold for anomaly detection
# 2.5 = production value. Lower to 1.5 for development testing only.
ANOMALY_ZSCORE_THRESHOLD=2.5

# Minimum severity for alerts
ALERT_SEVERITY_THRESHOLD=HIGH

# Set to true during development to skip real Claude API calls
# IMPORTANT: set to false before recording demo or deploying
USE_MOCK_REPORTS=true

# URL of the backend API — used by MCP server
BACKEND_URL=http://localhost:8000

# --- Frontend (Vite) ---
# These must be prefixed with VITE_ to be accessible in React
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/api/v1/ws
```

Now create your actual `.env` file by copying it:

```bash
cp .env.example .env
# Edit .env with your real values
```

Add `.env` to `.gitignore`. Open `.gitignore` and verify this line exists:

```
.env
```

**Done when:** `.env.example` is committed to Git. `.env` is NOT committed (verify with
`git status` — it should not appear as an untracked file if `.gitignore` is correct).

---

## Step 6 — Write docker-compose.yml

Create `infra/docker-compose.yml`:

```yaml
version: "3.9"

services:

  # ─── Database ───────────────────────────────────────────────
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    container_name: finpulse_db
    environment:
      POSTGRES_DB: finpulse
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d finpulse"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # ─── Redis ──────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: finpulse_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── Backend API ────────────────────────────────────────────
  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: finpulse_backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ../backend:/app   # mount for hot reload during dev
    env_file:
      - ../.env
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # ─── Celery Worker ──────────────────────────────────────────
  worker:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: finpulse_worker
    command: celery -A workers.celery_app worker --loglevel=info --concurrency=2
    volumes:
      - ../backend:/app
    env_file:
      - ../.env
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ─── Celery Beat (scheduler) ────────────────────────────────
  beat:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: finpulse_beat
    command: celery -A workers.celery_app beat --loglevel=info
    volumes:
      - ../backend:/app
    env_file:
      - ../.env
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ─── Frontend ───────────────────────────────────────────────
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: finpulse_frontend
    ports:
      - "5173:5173"
    volumes:
      - ../frontend:/app
      - /app/node_modules   # prevent host node_modules from overriding container
    env_file:
      - ../.env
    depends_on:
      - backend

volumes:
  timescaledb_data:
  redis_data:
```

**Important details explained:**

- `worker` and `beat` use the same Dockerfile as `backend` but different `command`
- The `volumes: ../backend:/app` mount enables hot reload — code changes reflect without rebuild
- `/app/node_modules` anonymous volume prevents your Mac's `node_modules` from conflicting with the container's
- `restart: unless-stopped` on worker and beat — if they crash, they restart automatically
- Health checks have `start_period` to give slow containers time to boot before being checked

**Done when:** `docker compose -f infra/docker-compose.yml config` runs without errors
(this validates the YAML structure without starting anything).

---

## Step 7 — Write infra/db/init.sql

This file runs automatically when the TimescaleDB container starts for the first time.

```bash
touch infra/db/init.sql
```

```sql
-- FinPulse — TimescaleDB initialization
-- This file runs once on container first start via docker-entrypoint-initdb.d
-- It only handles the TimescaleDB extension.
-- Hypertable creation and continuous aggregates are done AFTER
-- Alembic runs the migrations (Phase 1).

-- Enable the TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Notify that setup is complete
DO $$
BEGIN
  RAISE NOTICE 'TimescaleDB extension enabled. Run alembic migrations next.';
END $$;
```

**Why so minimal:** Alembic creates the actual tables in Phase 1. The hypertable
conversion and continuous aggregate must happen AFTER the tables exist. If we try to run
`create_hypertable` in init.sql before Alembic has created the table, it fails.
This file does only what must be done at container startup: enabling the extension.

**Done when:** File exists with the extension creation command.

---

## Step 8 — Write Nginx config

```bash
touch infra/nginx/nginx.conf
```

```nginx
# FinPulse Nginx Configuration
# Used in production to serve frontend and proxy API requests

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log;

    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;

        # Serve React frontend (built static files)
        root /usr/share/nginx/html;
        index index.html;

        # API requests → FastAPI backend
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # WebSocket upgrade — CRITICAL for real-time feed to work
        location /api/v1/ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;       # required for WS
            proxy_set_header Connection "upgrade";        # required for WS
            proxy_set_header Host $host;
            proxy_read_timeout 86400s;   # keep WS connections alive
        }

        # All other requests → React Router (SPA fallback)
        location / {
            try_files $uri $uri/ /index.html;
        }
    }
}
```

**Why the WebSocket headers matter:** Without `Upgrade` and `Connection: upgrade` headers,
Nginx treats the WebSocket connection as a regular HTTP request and immediately closes it.
Your real-time feed will silently fail in production if these are missing.

**Done when:** File exists. You don't need Nginx running locally during development —
this is for production deployment in Phase 8.

---

## Step 9 — Write backend Dockerfile

```bash
touch backend/Dockerfile
```

```dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# curl: used by health check
# gcc: needed by some Python packages that compile C extensions
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker caches this layer
# If requirements.txt doesn't change, this layer is reused on rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (overridden by docker-compose for worker and beat)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Now create `backend/requirements.txt` with everything the project needs:

```txt
# Web framework
fastapi==0.111.0
uvicorn[standard]==0.29.0

# Database
sqlalchemy==2.0.30
asyncpg==0.29.0          # async PostgreSQL driver
alembic==1.13.1
psycopg2-binary==2.9.9   # sync driver (used by Alembic)

# Settings
pydantic==2.7.1
pydantic-settings==2.2.1

# Background tasks
celery==5.3.6
redis==5.0.4

# Market data
yfinance==0.2.38
pandas==2.2.2

# AI
anthropic==0.26.0
langfuse==2.7.3

# Testing
pytest==8.2.0
pytest-asyncio==0.23.6
httpx==0.27.0

# Code quality
ruff==0.4.4
mypy==1.10.0
```

**Done when:** `docker build -t finpulse-backend ./backend` completes without errors.
Image exists in `docker images`.

---

## Step 10 — Write frontend Dockerfile

```bash
touch frontend/Dockerfile
```

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Copy package files first (layer caching)
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start dev server
# --host 0.0.0.0 is required to be accessible outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

Create a minimal `frontend/package.json` so Docker can build it:

```json
{
  "name": "finpulse-frontend",
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.2.10"
  }
}
```

Create a minimal `frontend/src/main.tsx` so the frontend container can actually start:

```tsx
import React from "react"
import ReactDOM from "react-dom/client"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <div style={{ fontFamily: "monospace", padding: "2rem" }}>
      <h1>FinPulse</h1>
      <p>Phase 0 — Frontend placeholder. Real UI in Phase 5.</p>
    </div>
  </React.StrictMode>
)
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FinPulse</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
})
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  },
  "include": ["src"]
}
```

**Done when:** `docker build -t finpulse-frontend ./frontend` completes without errors.

---

## Step 11 — Write minimal backend skeleton

Before Docker Compose can start the backend, it needs an importable FastAPI app.
Create these minimal files now. Real implementation is in Phase 4.

`backend/app/__init__.py` — empty file:
```bash
touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/api/v1/__init__.py
touch backend/workers/__init__.py
```

`backend/app/main.py` — minimal FastAPI app with health endpoint:

```python
from fastapi import FastAPI

app = FastAPI(title="FinPulse API", version="0.1.0")


@app.get("/api/v1/health")
async def health():
    """
    Health check endpoint.
    Phase 0: returns static response.
    Phase 4: will check real DB and Redis connections.
    """
    return {
        "status": "healthy",
        "db": "not_checked",
        "redis": "not_checked",
        "note": "Phase 0 stub — real health check implemented in Phase 4"
    }
```

**Done when:** `cd backend && python -c "from app.main import app; print('OK')"` prints OK.

---

## Step 12 — Write the Makefile

Create `Makefile` at the project root:

```makefile
# FinPulse Makefile
# All commands run from the project root.
# Usage: make <target>

COMPOSE = docker compose -f infra/docker-compose.yml
BACKEND = $(COMPOSE) exec backend
DB      = $(COMPOSE) exec timescaledb

.PHONY: dev build down logs test migrate migration lint shell db seed

# ─── Core ────────────────────────────────────────────────────

dev:
	$(COMPOSE) up --build

build:
	$(COMPOSE) build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

# ─── Database ────────────────────────────────────────────────

migrate:
	$(BACKEND) alembic upgrade head

migration:
	$(BACKEND) alembic revision --autogenerate -m "$(name)"
	@echo "Review the generated migration file before running make migrate"

db:
	$(DB) psql -U postgres finpulse

# ─── Testing ─────────────────────────────────────────────────

test:
	$(BACKEND) pytest tests/ -v --tb=short
	cd frontend && tsc --noEmit

test-backend:
	$(BACKEND) pytest tests/ -v --tb=short

test-frontend:
	cd frontend && tsc --noEmit

# ─── Code quality ────────────────────────────────────────────

lint:
	$(BACKEND) ruff check app/ workers/
	$(BACKEND) mypy app/ workers/ --ignore-missing-imports
	cd frontend && tsc --noEmit

# ─── Development utilities ───────────────────────────────────

shell:
	$(BACKEND) python

redis-cli:
	$(COMPOSE) exec redis redis-cli

# ─── Help ────────────────────────────────────────────────────

help:
	@echo ""
	@echo "FinPulse Makefile commands:"
	@echo ""
	@echo "  make dev          Start all 6 Docker services (with rebuild)"
	@echo "  make build        Build all Docker images"
	@echo "  make down         Stop all services"
	@echo "  make logs         Tail logs from all services"
	@echo ""
	@echo "  make migrate      Run alembic upgrade head"
	@echo "  make migration    Create new migration (pass name=your_description)"
	@echo "  make db           Open psql shell in TimescaleDB"
	@echo ""
	@echo "  make test         Run pytest + tsc --noEmit"
	@echo "  make lint         Run ruff + mypy + tsc"
	@echo ""
	@echo "  make shell        Open Python shell in backend container"
	@echo "  make redis-cli    Open redis-cli in Redis container"
	@echo ""
```

**Done when:** Running `make help` from the project root prints the help text without
errors.

---

## Step 13 — Write GitHub Actions CI pipeline

```bash
touch .github/workflows/ci.yml
```

```yaml
name: CI

on:
  push:
    branches: ["*"]
  pull_request:
    branches: ["main"]

jobs:

  # ─── Python linting ──────────────────────────────────────────
  ruff:
    name: Python lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install ruff
        run: pip install ruff==0.4.4
      - name: Run ruff
        run: ruff check backend/

  # ─── Python type checking ────────────────────────────────────
  mypy:
    name: Python types (mypy)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run mypy
        run: mypy backend/app backend/workers --ignore-missing-imports

  # ─── Python tests ────────────────────────────────────────────
  pytest:
    name: Python tests (pytest)
    runs-on: ubuntu-latest
    services:
      # Spin up real TimescaleDB for repo tests
      timescaledb:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_DB: finpulse_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: testpassword
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DB_HOST: localhost
      DB_PORT: 5432
      DB_NAME: finpulse_test
      DB_USER: postgres
      DB_PASSWORD: testpassword
      REDIS_URL: redis://localhost:6379/0
      ANTHROPIC_API_KEY: sk-ant-fake-key-for-ci
      LANGFUSE_PUBLIC_KEY: pk-lf-fake
      LANGFUSE_SECRET_KEY: sk-lf-fake
      LANGFUSE_HOST: https://cloud.langfuse.com
      TICKERS: TSLA,AAPL
      USE_MOCK_REPORTS: "true"
      ANOMALY_ZSCORE_THRESHOLD: "2.5"
      BACKEND_URL: http://localhost:8000
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: backend/requirements.txt
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run pytest
        working-directory: backend
        run: pytest tests/ -v --tb=short

  # ─── Frontend type check ─────────────────────────────────────
  typescript:
    name: Frontend types (tsc)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        working-directory: frontend
        run: npm install
      - name: Type check
        working-directory: frontend
        run: npx tsc --noEmit
```

**Key decisions in this file:**

- `ANTHROPIC_API_KEY: sk-ant-fake-key-for-ci` — CI never calls real Claude. `USE_MOCK_REPORTS=true` ensures this.
- Real TimescaleDB and Redis services run in CI — your repo tests test against a real DB, not mocks.
- `cache: "pip"` and `cache: "npm"` — speeds up CI by reusing dependency installs between runs.
- All 4 jobs run in parallel — total CI time is the slowest single job, not the sum of all.

**Done when:** File is committed and pushed. Go to GitHub → Actions tab → CI workflow
appears and all 4 jobs pass (they will pass trivially since tests/ is empty).

---

## Step 14 — Add .gitignore entries

Open `.gitignore` (it was created by GitHub when you initialized with Python template).
Add these lines:

```
# Environment
.env

# Python
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
.pytest_cache/

# Node
node_modules/
frontend/dist/
frontend/.vite/

# Docker
*.log

# IDE
.vscode/
.idea/
*.swp
```

**Done when:** `git status` does not show `.env` as an untracked file.

---

## Step 15 — Set up branch protection

1. Go to your GitHub repository
2. Settings → Branches → Add branch protection rule
3. Branch name pattern: `main`
4. Enable: **Require status checks to pass before merging**
5. Search for and select all 4 CI jobs: `ruff`, `mypy`, `pytest`, `typescript`
6. Enable: **Require branches to be up to date before merging**
7. Enable: **Do not allow bypassing the above settings**
8. Save

**Done when:** Create a test branch. Push a commit with a syntax error in Python.
Open a PR to main. CI fails. Merge button is blocked. Fix the error. CI passes. Merge
is now allowed.

---

## Step 16 — First commit and smoke test

Commit everything built so far:

```bash
git add .
git commit -m "Phase 0: Foundation — folder structure, Docker, CI, documentation"
git push origin main
```

Now do the full smoke test:

```bash
# Start all 6 services
make dev

# In a new terminal — check all services are running and healthy
docker compose -f infra/docker-compose.yml ps
```

Expected output — all 6 services showing `healthy` or `running`:

```
NAME                  STATUS          PORTS
finpulse_backend      Up (healthy)    0.0.0.0:8000->8000/tcp
finpulse_beat         Up              
finpulse_db           Up (healthy)    0.0.0.0:5432->5432/tcp
finpulse_frontend     Up              0.0.0.0:5173->5173/tcp
finpulse_redis        Up (healthy)    0.0.0.0:6379->6379/tcp
finpulse_worker       Up              
```

Test each service manually:

```bash
# Backend health endpoint
curl http://localhost:8000/api/v1/health
# Expected: {"status":"healthy","db":"not_checked",...}

# Frontend
open http://localhost:5173
# Expected: "FinPulse — Phase 0 — Frontend placeholder"

# Redis
docker exec finpulse_redis redis-cli ping
# Expected: PONG

# TimescaleDB
docker exec finpulse_db pg_isready -U postgres
# Expected: /var/run/postgresql:5432 - accepting connections

# Worker log — should show connected to Redis
docker logs finpulse_worker
# Expected: "[2026-...] Connected to redis://..."

# Beat log — should show scheduler running
docker logs finpulse_beat
# Expected: "beat: Starting..."
```

Now stop everything:

```bash
make down
# Expected: all containers stop cleanly
```

Start again to confirm it's repeatable:

```bash
make dev
# Expected: all 6 healthy again within 60 seconds
```

**Done when:** Both `make dev` → healthy + `make down` → clean stop work reliably
two times in a row. The second run is important — it confirms there are no one-time
setup issues.

---

## Phase 0 — Final checklist

Go through every item. Do not mark anything done until you have verified it manually.

**Repository:**
- [ ] GitHub repo exists and is public
- [ ] Branch protection is active — CI must pass before merging to main
- [ ] `.env` is NOT visible on GitHub (only `.env.example` is committed)
- [ ] CI pipeline runs on push and all 4 jobs pass

**Documentation:**
- [ ] `ARCHITECTURE.md` — all 6 decisions written in your own words with reasoning
- [ ] `api-contracts.md` — every route documented with all request/response shapes
- [ ] `.env.example` — every environment variable documented with description

**Infrastructure:**
- [ ] All 34 folders exist (run `find . -type d | grep -v .git | grep -v node_modules | wc -l`)
- [ ] `infra/docker-compose.yml` — 6 services, health checks on timescaledb/redis/backend
- [ ] `infra/db/init.sql` — enables TimescaleDB extension
- [ ] `infra/nginx/nginx.conf` — includes WebSocket upgrade headers
- [ ] `backend/Dockerfile` — builds without errors
- [ ] `frontend/Dockerfile` — builds without errors
- [ ] `Makefile` — all targets work from project root

**Running system:**
- [ ] `make dev` — all 6 containers healthy within 60 seconds
- [ ] `curl http://localhost:8000/api/v1/health` — returns JSON
- [ ] `open http://localhost:5173` — shows placeholder page
- [ ] `make down` — all containers stop cleanly
- [ ] Second `make dev` after `make down` — works identically

---

## What you should NOT do in Phase 0

These are the most common mistakes that cost hours later:

**Do not start Phase 1 if worker or beat containers are crashing.** Check their logs with
`docker logs finpulse_worker`. If they're crashing because Celery can't import the app,
you have an import error — fix it before moving on.

**Do not skip writing ARCHITECTURE.md.** You will be asked to explain every decision in
this file in interviews. Write it now while the reasoning is fresh from reading the
architecture document. It takes 30 minutes and saves you 3 hours of interview panic.

**Do not commit `.env`.** Check `git status` before every commit. If `.env` ever gets
committed with a real API key, rotate that key immediately — GitHub scans for exposed
secrets.

**Do not use docker-compose (v1) instead of docker compose (v2).** The hyphenated version
is deprecated. The commands in this document use `docker compose` (space, no hyphen).

---

## Moving to Phase 1

You are ready to start Phase 1 when:

1. `make dev` produces 6 healthy containers every time
2. `git log --oneline` shows your Phase 0 commit on main
3. CI is green on GitHub
4. You can explain all 6 architecture decisions without reading the document

Phase 1 starts with the database schema. Do not write a single model until you have
verified Phase 0 is completely solid.
