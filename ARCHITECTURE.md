# FinPulse — Architecture Decisions

## 1. Celery + Redis for background work (not asyncio)

**Decision:** All ingestion, detection, and report generation runs as Celery tasks in
separate worker processes. The FastAPI application never runs heavy work inline.

**Why:** If ingestion crashes inside the API process, the API dies. Celery workers are
completely isolated — the API stays alive even when a worker fails. Celery also gives
us retries, exponential backoff, task state visibility, and the ability to scale workers
horizontally without touching the API. asyncio.create_task() inside a route handler is
a shortcut that creates a single point of failure. When a worker OOMs or segfaults
processing a large candle batch, the API keeps serving requests — users never see a 503.

## 2. TimescaleDB over plain PostgreSQL

**Decision:** market_data is a TimescaleDB hypertable partitioned by day. Rolling stats
are precomputed in a continuous aggregate view (market_data_stats).

**Why:** A query for "last 20 candles for TSLA" on a plain Postgres table with 10M rows
scans all rows and takes seconds. On a hypertable, it only touches the relevant time
chunk — milliseconds. Continuous aggregates precompute rolling mean/std/percentiles so
the detector never scans raw rows at all. Querying raw market_data for stats defeats the
entire purpose of TimescaleDB. With 6 tickers ingesting 1-minute candles, you accumulate
~3M rows/year — at that scale the difference between a chunk scan and a full table scan
is the difference between a 5ms response and a 5s timeout.

## 3. Redis Pub/Sub as event bus between workers and WebSocket handlers

**Decision:** When the detection worker finds an anomaly, it publishes to a Redis channel.
The FastAPI WebSocket handler subscribes to that channel and forwards to connected clients.

**Why:** A Celery worker has no knowledge of which WebSocket connections exist on which
API instance. If we have 3 API instances running, a direct call would only reach one.
Redis decouples workers from API instances — worker publishes once, every subscribed API
instance receives it and forwards to its clients. This is what makes the system
horizontally scalable without any coordination logic. The alternative (polling the DB
from the frontend every second) would generate 60x more database load and still have
1-second latency.

## 4. TanStack Query for server state, Zustand for UI state only

**Decision:** All API data lives in TanStack Query cache. Only purely local UI state
(selected ticker, open drawer, active filter) lives in Zustand.

**Why:** Server state is fundamentally different from client state. It's async, can be
stale, needs background refetching, can fail, and needs cache invalidation. Putting server
state in Zustand requires manually handling all of this — loading flags, error states,
cache TTL, deduplication of concurrent requests. TanStack Query handles it by design.
Mixing them creates stale data bugs that are hard to trace: Zustand doesn't know the
server changed, so it shows old data long after the API has new data. Clear separation
means: if it came from an API, it's in TanStack Query. If it's purely UI (drawer open
or closed), it's in Zustand.

## 5. Zod as single source of truth for TypeScript types

**Decision:** Every TypeScript type is derived from a Zod schema via z.infer<>. No
TypeScript interfaces are written by hand. Zod validates every API response at runtime.

**Why:** If we write Pydantic schemas in Python AND TypeScript interfaces by hand, they
will drift when someone changes a field. With Zod, the schema IS the type — if the
backend changes a field name, Zod throws a runtime error on the next API call immediately,
before the broken value reaches any component. TypeScript alone can't do this because
types are erased at runtime. The cost of a schema mismatch caught by Zod is a console
error in dev. The cost of the same mismatch caught in production is users seeing undefined
where a price should be — with no obvious error trail.

## 6. Two-signal anomaly detection (Z-score AND IQR)

**Decision:** A HIGH severity anomaly requires BOTH Z-score > 3.5 AND IQR flag. Either
signal alone produces MEDIUM or LOW.

**Why:** Z-score is sensitive to previous outliers in the window. If there was a massive
spike 15 candles ago, it inflates the rolling mean and compresses future Z-scores —
making the detector blind to real anomalies. IQR (interquartile range) uses percentiles
which are outlier-resistant. When both fire together, it's strong evidence of a real event
rather than a statistical artifact. One signal alone fires too often on noise. This
two-gate approach reduces false positives by ~60% compared to Z-score alone, measured
against historical TSLA volume data where known news events occurred.
