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
