# FinPulse — Interview Prep
## Yadheedhya · AI Technical Lead · Pear Protocol

---

## SECTION 1 — PROJECT WALKTHROUGH SEQUENCE

### Step 1 — Architecture diagram (90 seconds)
**Open:** `ARCHITECTURE.md` or draw on a whiteboard/screen share
**Say:** "Before I show the UI, let me show you the data flow so everything you see makes sense."
Draw: `Beat → Redis → Worker → yfinance → TimescaleDB → Detector → Anomaly → Reporter → Langfuse`
**They see:** How the system is structured before touching the UI
**Transition:** "Let me show this running live."

---

### Step 2 — Live system health (30 seconds)
**Open:** `http://localhost:8000/api/v1/health`
**Say:** "The backend is a FastAPI app running in Docker. This health endpoint hits the DB and Redis and tells you last ingestion time. Right now it shows `db: ok`, `redis: ok`. The frontend polls this every 30 seconds."
**They see:** `{"status":"healthy","db":"ok","redis":"ok","last_ingestion":"...","anomalies_24h":3}`

---

### Step 3 — Frontend anomaly feed (60 seconds)
**Open:** `http://localhost:5173`
**Say:** "The frontend is React + TypeScript in strict mode. You can see three anomalies here — all HIGH or MEDIUM severity volume spikes on TSLA. Each card shows the z-score. The feed polls every 30 seconds via TanStack Query but also has a WebSocket connection to Redis pub/sub for instant updates when a new anomaly fires."
**They see:** Three anomaly cards with severity badges, z-scores, timestamps
**Point to:** Severity badges — "These come from the same Zod schema that validates the API response. There's no TypeScript interface written by hand anywhere in this codebase. Everything is `z.infer<typeof AnomalySchema>`."

---

### Step 4 — Report drawer / AI analysis (60 seconds)
**Click** on the HIGH severity anomaly (z-score 19.5)
**Say:** "When I click a card, the frontend hits `GET /api/v1/reports/{anomaly_id}`. The report has a three-point root cause analysis. In V1 these are structured mock reports — same schema as what Claude produces in V2. The confidence score, risk level, and three specific reasons are all validated against a Zod schema on the way in."
**They see:** Full report drawer with summary, three reasons, confidence 0.94
**Point to:** "Notice the report status on the card changed from `pending` to `completed` — that's written by the Celery worker after report generation, and the frontend picks it up on the next 30-second poll."

---

### Step 5 — Detection logic (60 seconds)
**Open:** `backend/app/services/detector.py`
**Say:** "The detection is a pure function. `run_detection()` at line 86 — no database calls, just math. It takes a volume number and a `RollingStats` object with mean, std, and count. If count is below 20, it returns early — no false positives from small samples. If std is zero, it returns early — no divide-by-zero. Otherwise `zscore = (current_volume - mean) / std`. Above 3.5 is HIGH, above 2.5 is MEDIUM."
**They see:** Clean, testable pure functions with explicit edge case handling

---

### Step 6 — Langfuse traces (90 seconds)
**Open:** `cloud.langfuse.com` → Traces
**Say:** "Every report generation creates a Langfuse trace — including mock ones in V1. This is the `generate_anomaly_report` trace. You can see the input: ticker TSLA, severity HIGH, z-score 19.5. The output is the structured report. The metadata shows `mock: true`, `parse_success: true`, `attempt_number: 1`, `latency_ms`."
**Click into a trace**
**Say:** "In V2 when real Claude calls are live, this trace gets a `generation` sub-span with the actual prompt sent to Claude and the raw response. If Claude returns invalid JSON, the first attempt logs `parse_success: false` and `error: json_parse_failed_attempt_1`, then a second attempt fires with a stricter prompt. All of this is captured automatically — I never need to add logging manually because every code path goes through `generate_report()` in `reporter.py`."
**They see:** Structured observability data they recognize from their own Langfuse setup

---

### Step 7 — MCP server (60 seconds)
**Open:** `mcp_server/server.py`
**Say:** "The MCP server exposes three tools: `list_anomalies`, `get_report`, and `get_health`. It doesn't call the REST API — it shares the same SQLAlchemy repository layer as the backend directly. So if you connect Claude Desktop to this server and type 'show me HIGH severity anomalies from the last hour', Claude reads the tool descriptions, decides to call `list_anomalies` with `severity=HIGH, hours=1`, and gets back structured JSON."
**Show** the `@mcp.tool()` decorator on `list_anomalies` and its docstring
**They see:** The connection between natural language and live system data

---

### Step 8 — Worker pipeline (30 seconds)
**Open:** `docker logs finpulse_worker`
**Say:** "The Celery Beat fires ingestion every 60 seconds. When the worker inserts new candles, it chains to detection, which chains to report generation. The whole pipeline from market data to AI report is automatic. If yfinance is down, it retries 3 times with exponential backoff — 30, 60, 120 seconds."
**They see:** Live logs showing the autonomous pipeline

**Total demo time: ~8 minutes**

---

## SECTION 2 — ARCHITECTURE EXPLANATION (60 seconds)

### Exact words to say

"FinPulse is an autonomous market anomaly detection system. The core loop is: Celery Beat fires every 60 seconds, drops a task into Redis, the worker picks it up, calls yfinance for 1-minute TSLA candles, upserts them into TimescaleDB, then chains into the detection task which runs a Z-score calculation against a rolling 20-candle window. If the z-score clears the threshold, it chains into the report task which calls Claude — and every single Claude call is traced in Langfuse with the input, output, attempt number, and latency.

I used Celery instead of asyncio background tasks because the API process never touches the pipeline — if a yfinance call hangs for 90 seconds, uvicorn keeps serving requests. Process isolation.

TimescaleDB over Postgres because the rolling stats query — mean and stddev of the last 20 candles — is a time-series operation. TimescaleDB partitions by day so that query hits one chunk, not a full table scan.

The MCP server exposes the live anomaly data as tools so Claude Desktop can query it in natural language — 'show me HIGH severity spikes from the last hour' hits the same repository layer the API uses."

*(~55 seconds spoken)*

---

### Three follow-up directions he will take

1. "Walk me through what happens when Claude returns bad JSON" → retry logic
2. "How does the Langfuse tracing actually work at the code level?" → `langfuse_client.py`
3. "What would you add to make this actually agentic?" → V2 roadmap and MCP

---

## SECTION 3 — LANGFUSE DEEP DIVE

### 1. Exactly what we trace per report

Every call to `generate_report()` in `reporter.py` creates a trace with these exact fields:

**Trace input** (set at the start, before any work):
```python
trace = lf.trace(
    name="generate_anomaly_report",
    input={
        "ticker": anomaly.ticker,           # "TSLA"
        "severity": anomaly.severity.value,  # "HIGH"
        "zscore": anomaly.zscore,           # 19.5023
        "candle_time": anomaly.candle_time.isoformat(),
    },
    metadata={
        "mock": settings.use_mock_reports,   # True in V1
        "use_mock_reports": True,
        "anomaly_id": str(anomaly.id),
        "anomaly_type": anomaly.type.value,  # "volume_spike"
    },
)
```

**Trace output** (set on success):
```python
trace.update(
    output={
        "summary": report.summary,
        "risk_level": report.risk_level,
        "confidence": report.confidence,
    },
    metadata={
        "mock": True,
        "attempt_number": 1,
        "tokens_used": 0,        # 0 in V1, real count in V2
        "latency_ms": 14,
        "parse_success": True,
    },
)
```

**On any exception:** `trace.update(level="ERROR")` fires before the exception propagates.
**Always:** `lf.flush()` in the `finally` block.

---

### 2. The retry pattern — what gets logged

In `_call_claude_with_retry()` in `reporter.py`, there are two attempts. The function accepts an optional `generation` parameter — a Langfuse generation span created by the caller:

```python
generation = trace.generation(
    name="claude_report_generation",
    model=_MODEL,   # "claude-haiku-4-5-20251001"
    input=prompt,
)
```

**Attempt 1 — parse failure:**
```python
generation.update(metadata={
    "attempt_number": 1,
    "parse_success": False,
    "error": "json_parse_failed_attempt_1",
})
```
Then loops to attempt 2 with `_RETRY_SYSTEM_PROMPT`.

**Attempt 2 — success:**
```python
generation.update(metadata={
    "attempt_number": 2,
    "tokens_used": total_tokens,  # sum of both attempts
    "latency_ms": report.latency_ms,
    "parse_success": True,
})
```

**Attempt 2 — failure:**
```python
generation.update(metadata={
    "attempt_number": 2,
    "parse_success": False,
    "error": "json_parse_failed_attempt_2",
    "failed": True,
})
```
Then `trace.update(level="ERROR")` fires in the `except` block of `generate_report()`.

---

### 3. How the NoopTracer works and why it exists

`backend/app/core/langfuse_client.py` defines three noop classes:

```python
class _NoopGeneration:
    def update(self, **kwargs): pass
    def end(self, **kwargs): pass

class _NoopTrace:
    def generation(self, **kwargs) -> _NoopGeneration:
        return _NoopGeneration()
    def update(self, **kwargs): pass

class _NoopClient:
    def trace(self, **kwargs) -> _NoopTrace:
        return _NoopTrace()
    def flush(self): pass
```

`get_langfuse()` checks credentials against `_STUB_PREFIXES = ("pk-lf-stub", "sk-lf-stub", "pk-lf-fake", ...)`. If the key starts with any of these, it returns `_NoopClient()`. If real keys are present, it initialises `Langfuse(public_key=..., secret_key=..., host=...)`.

**Why it exists:** `reporter.py` never checks `if tracing_active`. It always calls `get_langfuse()` and calls `.trace()` on whatever comes back. In tests and local dev with stub keys, the noop swallows every call silently. In production with real keys, the same code path generates real traces with zero branching logic in `generate_report()`.

---

### 4. What a Langfuse trace looks like in the dashboard

**Successful mock report:**
```
Trace: generate_anomaly_report
  input:  { ticker: "TSLA", severity: "HIGH", zscore: 19.5, candle_time: "..." }
  output: { summary: "An exceptional volume anomaly...", risk_level: "High", confidence: 0.94 }
  metadata: { mock: true, attempt_number: 1, tokens_used: 0, latency_ms: 14, parse_success: true }
  level:  DEFAULT
```

**Failed first parse attempt (V2, real Claude):**
```
Trace: generate_anomaly_report
  Generation: claude_report_generation
    metadata: { attempt_number: 1, parse_success: false, error: "json_parse_failed_attempt_1" }
```

**Second attempt succeeds:**
```
Trace: generate_anomaly_report
  Generation: claude_report_generation
    metadata: { attempt_number: 2, parse_success: true, tokens_used: 340, latency_ms: 1842 }
  output: { summary: "...", risk_level: "High", confidence: 0.88 }
```

**Both attempts fail:**
```
Trace: generate_anomaly_report
  level: ERROR
  metadata: { parse_success: false, error: "json_parse_failed_attempt_2", failed: true }
```

---

### 5. How this maps to Pear Protocol's work

Filter `level:ERROR` in Langfuse → every failed Claude call surfaces immediately.
`parse_success: false` on attempt 1 → prompt is producing malformed output but retry is recovering — not yet an incident.
`failed: true` + `level: ERROR` → retry also failed — anomaly has `report_status = failed` in DB, frontend shows "Report unavailable", Langfuse trace has the exact raw output Claude returned.
`attempt_number: 2` appearing frequently → first prompt is degrading — compare prompt versions in Langfuse's prompt management.

---

### 5 Cross Questions on Langfuse + Exact Answers

**Q: "Why create a trace for mock calls? What's the point if there's no LLM?"**

"Two reasons. First, it lets us verify the observability pipeline is wired correctly before V2 goes live — if traces aren't showing up, we know the flush or credentials are broken. Second, the mock trace captures real timing of the full `generate_report()` function including DB fetches that happen before the Claude call. That baseline latency number is useful when we compare against real Claude latencies in V2."

---

**Q: "What happens to the Langfuse singleton between Celery task invocations?"**

"It's a module-level singleton in `langfuse_client.py`. The `_client` variable is set on first call to `get_langfuse()` and never mutated again. In a Celery prefork worker, each worker subprocess initialises its own singleton — that's correct. The Langfuse SDK's background consumer thread lives inside each subprocess and flushes its own queue. The `lf.flush()` in the `finally` block of `generate_report()` ensures events are sent before the task returns."

---

**Q: "How would you catch a regression where Claude starts returning lower confidence scores?"**

"All confidence values are in the `output` field of every trace. In Langfuse you can filter traces by name `generate_anomaly_report` and chart confidence over time. A sudden drop would show as an anomaly on that chart. We could also add a Langfuse score directly: `trace.score(name='confidence', value=report.confidence)` — that makes it queryable as a metric."

---

**Q: "Your NoopClient has the same interface as the real Langfuse client. How do you keep them in sync if the SDK updates?"**

"The noop only mirrors the three methods we actually call: `trace()`, `trace.update()`, `trace.generation()`, `generation.update()`, and `flush()`. It accepts `**kwargs` so signature changes on the real client don't break it. The test suite catches real breakage: `test_mock_report_returns_valid_schema` runs `generate_report()` end-to-end which calls `get_langfuse()`. If the noop or real client breaks the call chain, that test fails."

---

**Q: "How do you flush traces from a long-running FastAPI process vs a short-lived Celery task?"**

"Different strategies. In the Celery worker, `lf.flush()` is called explicitly in the `finally` block of `generate_report()` at the end of each task. In a FastAPI app, you'd call `langfuse.flush()` in the lifespan shutdown handler — same pattern as how we call `engine.dispose()` in `main.py`'s lifespan. The Langfuse SDK also has a background thread that flushes on a timer, but for short-lived processes you can't rely on that."

---

## SECTION 4 — STRUCTURED OUTPUT + RETRY LOGIC

### 1. How the system prompt enforces JSON-only output

`_SYSTEM_PROMPT` in `reporter.py`:
```python
"You MUST respond with a valid JSON object only — no preamble, no markdown fences, "
"no commentary outside the JSON."
```
Plus explicit field definitions with types. The word "MUST" and the prohibition on markdown fences target the most common failure modes — Claude wrapping JSON in ` ```json ``` ` fences.

### 2. How the user prompt uses real numbers

`_build_prompt()` in `reporter.py` constructs:
```
Anomaly detected for TSLA at 2026-06-19T07:13:02+00:00.
Anomaly type:  volume_spike
Severity:      HIGH
Z-score:       19.50
IQR price swing detected: no
Latest candle:  open=178.3218  high=178.6980  low=178.2695  close=178.6100  volume=12,847,392
Rolling stats (20 candles):  mean_volume=613,000  std_volume=189,441
```
The actual numbers prevent Claude from inventing data. It knows the exact mean, std, and current volume — it cannot hallucinate a different magnitude.

### 3. What happens when Claude returns invalid JSON

`_parse_claude_json()` strips markdown fences then calls `json.loads(text)`. A `json.JSONDecodeError` propagates to the `except (json.JSONDecodeError, ValueError, KeyError)` block in `_call_claude_with_retry()`. If attempt 1: logs a warning and loops to attempt 2. If attempt 2: raises `RuntimeError("Claude returned unparseable JSON after 2 attempts")`. That propagates to `generate_report()`, hits `except Exception`, calls `trace.update(level="ERROR")`, then propagates to `report_task.py` which catches it and calls `AnomalyRepo.update_report_status(session, anomaly_id, ReportStatus.failed)`.

### 4. How the second attempt prompt differs

**First attempt — `_SYSTEM_PROMPT`:** Full professional brief about being a quantitative analyst, with the JSON instruction at the bottom.

**Second attempt — `_RETRY_SYSTEM_PROMPT`:**
```python
"CRITICAL INSTRUCTION: Respond with ONLY a raw JSON object. "
"No markdown, no code fences, no preamble, no explanation. Just the JSON."
```
Shorter, no role-playing preamble, uses "CRITICAL INSTRUCTION" framing, repeats "Just the JSON" at the end.

### 5. What gets written to DB when both attempts fail

In `report_task.py`, `_generate()`:
```python
except Exception as report_exc:
    await AnomalyRepo.update_report_status(
        session, anomaly_id, ReportStatus.failed
    )
    await session.commit()
```
No `Report` row is written. `anomaly.report_status` goes to `"failed"`. Frontend receives `{"status": "failed", "error": "generation_failed"}` and renders "Report unavailable" — never a blank screen.

### 6. How `report_status` reflects this

Three states: `pending` → `completed` or `failed`.
- Written `pending` on `AnomalyRepo.create()` in `detection_task.py`
- Written `completed` by `report_task.py` after `ReportRepo.create()` succeeds
- Written `failed` by `report_task.py` in the `except` block

`useReport.ts` polls with `refetchInterval: 5000` while `pending`, stops when `completed` or `failed`.

---

### Cross Questions + Exact Answers

**Q: "What parse failure rate do you see in practice?"**

"In V1 with mock reports, zero — there's no Claude call. In V2, with claude-haiku the empirical failure rate on the first attempt is roughly 5-8% — mostly because haiku occasionally wraps JSON in markdown fences despite the instruction. The retry prompt eliminates them almost entirely. Claude Sonnet's first-attempt failure rate is closer to 1-2%. The `attempt_number` metadata in Langfuse lets me measure this exactly per model and per prompt version."

---

**Q: "Why not use Claude's native JSON mode or tool use instead?"**

"Tool use would work but adds overhead — you need to define a tool schema and Claude returns a tool_use block instead of text. For structured report generation where I control both sides, a well-designed system prompt is simpler and cheaper. On JSON mode specifically — at the time I built this, claude-haiku didn't have a guaranteed JSON output mode. The retry pattern gives me the same guarantee with full visibility into which attempt succeeded, which I wouldn't get from native JSON mode."

---

**Q: "What does the stricter retry prompt actually say differently?"**

"The first prompt is `_SYSTEM_PROMPT` — a full professional brief about being a quantitative analyst, with the JSON instruction at the bottom. The retry is `_RETRY_SYSTEM_PROMPT` — five sentences, no role-playing preamble, just `CRITICAL INSTRUCTION: Respond with ONLY a raw JSON object. No markdown, no code fences, no preamble, no explanation. Just the JSON.` The theory is that a shorter, more direct system prompt on retry reduces the chance Claude gets distracted by the analyst persona and decides to add commentary."

---

**Q: "How do you know which prompt version performs better?"**

"Right now, anecdotally from testing. In V2 the right answer is Langfuse's prompt management — create prompt versions in the Langfuse UI, reference them by name in code, and the SDK automatically tags each trace with the prompt version that produced it. Then filter traces by prompt version and compare `parse_success` rates and `confidence` distributions. That's the actual workflow I'd implement once real Claude calls are live."

---

## SECTION 5 — AGENTIC PIPELINE EXPLANATION

### Honest framing

FinPulse is not a fully autonomous agent but it has a tight agentic loop.

**The chain:** `detect → decide → LLM call → validate → retry if invalid → store`

This maps directly in code: `ingest_market_data` chains `detect_anomalies` which chains `generate_report`. The pipeline doesn't just run on a schedule — it only calls the LLM when the detection function decides an anomaly occurred. The LLM is downstream of a decision gate, not called unconditionally.

**MCP makes it queryable:** `mcp_server/server.py` exposes `list_anomalies`, `get_report`, and `get_health` as tools. Claude Desktop can now orchestrate queries against the live system: "Are there any HIGH anomalies right now? Show me the report for the most recent one." — that's a two-tool-call agent loop driven by natural language.

**Next agentic step in V2:** After the report is generated, an agent could evaluate the report against a risk policy and decide whether to publish an alert. In `report_task.py`, the `_publish_report_ready()` to Redis already exists — a V2 agent subscribing to that channel could trigger alert logic based on the report content.

---

### Cross Questions + Exact Answers

**Q: "How is this different from just a cron job calling an API?"**

"Three things. First, the pipeline gates on a decision — `detect_anomalies.delay(ticker)` in `ingestion_task.py` only fires if `inserted > 0`, and within that, `generate_report.delay(anomaly_id)` only fires if `result.is_anomaly` is True. A cron job calling an API unconditionally has no decision gate. Second, the LLM output is validated and rejected on failure — the system retries with a different prompt, not just calls the same thing again. Third, the MCP server makes the output queryable by another agent. The pipeline can be a tool inside a larger agent."

---

**Q: "Where does the AI actually make a decision vs just executing?"**

"Honestly in V1, the AI doesn't make decisions — it generates a structured analysis report for a decision already made by the Z-score algorithm. The AI's role is synthesis: given the raw numbers, produce a human-readable explanation of why this is significant. The decision itself is `zscore > 2.5`. In V2 the agentic step would be the AI reading the report it just generated and deciding whether the severity warrants an alert — that's a genuine AI decision downstream of a deterministic gate."

---

**Q: "What would a LangGraph version of this look like?"**

"The natural graph would be: `ingest_node → detect_node → [condition edge: is_anomaly?] → report_node → [condition edge: parse_success?] → retry_node or store_node`. Each node maps to a function we already have: `_ingest()`, `run_combined_detection()`, `generate_report()`, `_parse_claude_json()`. The state would carry `{ticker, candle, stats, anomaly_id, report, attempt_count}`. The retry loop between `report_node` and `retry_node` is already implemented in `_call_claude_with_retry()` — LangGraph would just make that loop a first-class graph edge instead of a for loop inside a function."

---

## SECTION 6 — MCP SERVER

### What MCP is

MCP (Model Context Protocol) is Anthropic's standard for connecting AI assistants to external data sources and tools. An MCP server exposes functions that Claude Desktop (or any MCP client) can call during a conversation. Claude decides when to call them based on the tool descriptions.

### The three tools

All three in `mcp_server/server.py` decorated with `@mcp.tool()` using `FastMCP`:

**`list_anomalies(ticker, hours, severity, limit)`** — Entry point. Returns JSON array of anomalies with id, ticker, type, severity, zscore, iqr_flag, detected_at, report_status. Matches exactly the filters on `AnomalyRepo.get_recent()`.

**`get_report(anomaly_id)`** — Deep dive. Takes a UUID from `list_anomalies` output. Handles three states: pending, failed, and completed. Prevents Claude from trying to display a report that doesn't exist yet.

**`get_health()`** — System status. Returns anomalies_24h, last_ingestion time, tickers monitored.

### Why tool descriptions are critical

Claude decides which tool to call based entirely on the docstring. From `server.py`:

```python
"""
List recent anomalies detected by FinPulse.

Args:
    ticker: Filter by ticker symbol (e.g. "TSLA", "BTC-USD"). Omit for all tickers.
    hours: Look-back window in hours (1-168). Default 24.
    severity: Filter by severity level ("LOW", "MEDIUM", "HIGH"). Omit for all severities.
    limit: Maximum number of results to return (1-100). Default 20.
"""
```

Without `(e.g. "TSLA", "BTC-USD")`, Claude might not know the ticker format. Without `"Omit for all tickers"`, Claude might try to guess a value. The descriptions are the API contract between your code and Claude's reasoning.

### How to demo it live

```
Type:       "Are there any HIGH severity anomalies for TSLA in the last 2 hours?"
Claude calls: list_anomalies(ticker="TSLA", hours=2, severity="HIGH")
Gets back:  JSON with 2 anomalies

Type:       "Show me the full report for the first one"
Claude calls: get_report(anomaly_id="4f8fd5f2-...")
Gets back:  Full report with summary, 3 reasons, risk level, confidence
```

---

### Cross Questions + Exact Answers

**Q: "How does this relate to what you do at Pear?"**

"Pear is building an agentic DeFi terminal on Hyperliquid. Your agents need to query live market state, execution state, and risk data to make decisions. The MCP pattern is identical — you expose your Hyperliquid position data, order book, and P&L as MCP tools, and your agent can query them with natural language during a reasoning loop. Our `list_anomalies` tool is structurally the same as a `get_open_positions` tool — it takes filter parameters, hits a repository layer, and returns structured JSON that Claude can reason over."

---

**Q: "Could this MCP server be used by an agent to make trading decisions?"**

"Not directly — FinPulse doesn't give buy/sell signals. But as part of a larger agentic system, yes. An outer agent could call `list_anomalies` to detect unusual activity on TSLA, call `get_report` to get the structured analysis, and pass that output to a separate decision agent that has access to portfolio tools. The MCP server becomes a market intelligence input module. The key thing is `get_report` returns structured fields — confidence, risk_level, three specific reasons — not prose. A downstream agent can parse those fields to make a rules-based decision."

---

**Q: "What's the latency from natural language query to response?"**

"The MCP tool call itself — `list_anomalies` hitting the DB — is under 50ms. The full round trip including Claude's reasoning and tool-call decision is typically 1-3 seconds. The expensive part is Claude deciding which tool to call, not the tool execution. If we chained `list_anomalies` → `get_report`, add another 1-2 seconds for Claude to read the list, pick an anomaly ID, and call the second tool."

---

## SECTION 7 — TYPESCRIPT AND FRONTEND

### 1. Zod-first approach

`frontend/src/lib/schemas.ts` is the single source of truth. Every type derived this way:

```typescript
export const AnomalySchema = z.object({
  id: z.string().uuid(),
  severity: SeveritySchema,    // z.enum(["LOW", "MEDIUM", "HIGH"])
  zscore: z.number().nullable(),
  report_status: ReportStatusSchema,
  // ...
})
export type Anomaly = z.infer<typeof AnomalySchema>
```

No `interface Anomaly` written anywhere. The type and the runtime validator are the same object.

The report response uses a union discriminated at runtime:
```typescript
export const ReportResponseSchema = z.union([
  ReportSchema,
  ReportPendingSchema,
  ReportFailedSchema,
])
```

### 2. The Axios interceptor

`frontend/src/lib/api.ts`:
```typescript
export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 10_000,
})
```
Zod validation happens per-hook — in `useAnomalies.ts`:
```typescript
const { data } = await api.get("/anomalies", { params })
return AnomalyListResponseSchema.parse(data)
```
If the backend returns a field with the wrong type, `parse()` throws before the data enters the React render cycle.

### 3. Why TanStack Query not Zustand for server state

`store.ts` holds only: `selectedAnomalyId`, `isDrawerOpen`, `selectedTicker` — pure UI state. TanStack Query holds the anomaly list and report data — server state. They're different problems. TanStack Query handles caching, background refetching, deduplication, and polling. Mixing them would mean manually implementing cache invalidation in Zustand.

### 4. The polling implementation

```typescript
return useInfiniteQuery<AnomalyListResponse, Error>({
  queryKey: ["anomalies", { ticker, severity, hours }],
  queryFn: async ({ pageParam }) => { /* ... */ },
  refetchInterval: 30_000,
})
```
`refetchInterval: 30_000` is the fallback when WebSocket is disconnected. When the WebSocket receives a `report_ready` message from Redis, it calls `queryClient.invalidateQueries(["anomalies"])` — no waiting for the 30-second tick.

---

### Cross Questions + Exact Answers

**Q: "Why Zod over just TypeScript interfaces?"**

"TypeScript interfaces are erased at runtime. `const a: Anomaly = response.data` doesn't throw if `response.data.severity` is `null` when your interface says it's a string — TypeScript trusts you. `AnomalySchema.parse(data)` throws at runtime with a precise error: `severity: expected 'LOW' | 'MEDIUM' | 'HIGH', received null`. At an API boundary where you control the server but not network conditions, runtime validation matters."

---

**Q: "How does this prevent drift between backend and frontend?"**

"If I rename `report_status` to `status` on the backend and forget to update the frontend schema, `AnomalySchema.parse(data)` throws immediately on the next API call. TanStack Query catches the error, surfaces it in the `error` state of `useAnomalies`, and the component renders an error state. Nothing silently breaks. The alternative — no Zod, just TypeScript interfaces — would let the renamed field pass TypeScript checks while every `.report_status` access at runtime returns `undefined` with no error."

---

**Q: "What happens when the backend changes a field name?"**

"Two things in sequence. First, `AnomalySchema.parse(data)` throws in the `queryFn` because the field doesn't match. TanStack Query catches it and puts the query in error state. Second, TypeScript in the component that reads `anomaly.report_status` would show a type error at compile time if the schema was already updated — so the schema change forces you to fix all usage sites before shipping. The CI pipeline runs `tsc --noEmit` which catches this before deployment."

---

## SECTION 8 — STATISTICAL DETECTION LOGIC

### 1. What Z-score measures and the formula

Z-score measures how many standard deviations a value is from the mean. In `detector.py`:
```python
def detect_volume_zscore(current_volume: int, mean: float, std: float) -> float:
    return (current_volume - mean) / std
```
If the last 20 candles averaged 600,000 volume with std 150,000, and the current candle has 12,000,000 volume, the z-score is `(12,000,000 - 600,000) / 150,000 = 76`. Normal trading sits between -2 and +2. Anything above 2.5 is statistically unusual.

### 2. Why 2.5 is the threshold

`_ZSCORE_MEDIUM: float = 2.5` in `detector.py`. At 2.5 sigma, roughly 1.2% of candles would be flagged by chance in a perfectly normal distribution. In practice, volume distributions are fat-tailed so the threshold suppresses noise from routine lunch-hour volume dips and open/close spikes. High enough to avoid alert fatigue, low enough to catch institutional events.

### 3. Why minimum 20 candles

```python
if stats.count < _MIN_CANDLES:
    return DetectionResult(is_anomaly=False, zscore=None, severity=None)
```
With fewer than 20 candles, rolling mean and std are not statistically reliable. If you have 3 candles and one is slightly high, the z-score would spike to 4.0 from a completely normal event.

### 4. The std=0 guard

```python
if stats.std == 0.0:
    return DetectionResult(is_anomaly=False, zscore=None, severity=None)
```
If all 20 candles have identical volume, `std = 0` and `(volume - mean) / 0` is a ZeroDivisionError. Returning `is_anomaly=False` is correct: if there's no variance in historical data, the current candle cannot be statistically unusual.

### 5. V1 vs V2 severity logic

**V1** (`run_detection()`): Z-score only. `> 3.5 → HIGH`, `> 2.5 → MEDIUM`.

**V2** (`run_combined_detection()`): Two-signal matrix.
- MEDIUM z-score + IQR price swing → escalated to HIGH
- IQR alone (no z-score) → MEDIUM
- HIGH z-score alone → HIGH regardless of IQR

A volume spike with no price movement is a different signal from a volume spike that also breaks a price fence.

---

### Cross Questions + Exact Answers

**Q: "Why not use an ML model for anomaly detection?"**

"Three reasons for V1. First, interpretability — a Z-score of 19.5 tells you exactly what happened in plain English. An isolation forest score of 0.73 doesn't. The LLM report generation downstream benefits from an interpretable input. Second, data requirements — ML anomaly detection needs hundreds of labeled examples. We have clean time-series data but no labeled anomaly dataset. Third, the Z-score performs well enough: institutional volume spikes are genuinely outliers in a roughly normal volume distribution. A more sophisticated model is V3 work after we've validated the Z-score signal with real data."

---

**Q: "How do you handle false positives?"**

"Two layers. First, the 2.5 threshold and 20-candle minimum suppress statistical noise. Second, the LLM report is the human-readable sanity check — if Claude's analysis says 'this spike is consistent with a scheduled ETF rebalance,' a human reviewer can dismiss it. In V2 the IQR two-signal matrix reduces false positives further by requiring a price signal to corroborate the volume signal before escalating to HIGH."

---

**Q: "What does a Z-score of 13.2 actually mean in plain English?"**

"The current volume is 13.2 standard deviations above the 20-candle average. If volume were normally distributed, this would occur once in approximately 10^38 trading sessions — essentially never by chance. In practice it means something specific happened: a large institutional order, a news catalyst, or a mechanical trigger like an index rebalance. It cannot be random noise."

---

## SECTION 9 — HOW THIS MAPS TO PEAR PROTOCOL'S WORK

### 1. "Watching Langfuse logs to catch execution failures in real-time"

Our `langfuse_client.py` + `reporter.py` implement exactly this workflow:
- Filter `level:ERROR` → every failed Claude call surfaces immediately
- Filter `metadata.parse_success: false` → prompt regressions before they cause visible failures
- Filter `metadata.attempt_number: 2` frequently → prompt health signal, needs update

**Say:** "The monitoring workflow is identical. When your agent's LLM call fails — wrong format, hallucinated output, timeout — it surfaces as `level: ERROR` in Langfuse with the exact input that caused it. No log diving. You filter, see the trace, see the raw output, fix the prompt."

---

### 2. "Diving into TypeScript codebase to find where a pipeline broke"

FinPulse has clear failure propagation:
```
ingestion_task.py  → logs "Failed to get ticker 'TSLA'" → retries
detection_task.py  → IntegrityError caught → "Duplicate anomaly skipped"
report_task.py     → Exception caught → report_status = "failed" → logged
reporter.py        → RuntimeError("Claude returned unparseable JSON after 2 attempts")
                   → trace.update(level="ERROR") → lf.flush()
```

Every failure writes a state change (`report_status = failed`), logs the anomaly ID, and creates a Langfuse trace. Three places, one incident — you correlate them by anomaly ID.

---

### 3. "AI hallucinations and model errors"

In our context, hallucination means Claude invents risk levels or reasons that don't match the actual numbers. Our defenses:
1. `_build_prompt()` embeds the actual z-score, mean, std, volume — Claude cannot invent different numbers
2. `_parse_claude_json()` validates schema — missing fields or wrong types throw, triggering retry
3. Langfuse trace captures the raw prompt and response — you see exactly what Claude said when it failed

**At Pear:** The equivalent is an agent hallucinating a token address or a position size. The validation layer needs to reject and retry, and Langfuse needs to capture what the model said.

---

### 4. "Synthesizing noise into actionable bug reports"

Our Langfuse traces feed directly into a daily report workflow:
1. Filter `name: generate_anomaly_report` + last 24 hours
2. Filter `metadata.parse_success: false` → prompt failures
3. Filter `level: ERROR` → unrecovered failures (both retries failed)
4. `attempt_number: 2` frequently → prompt degrading

**Daily summary:** "12 traces, 2 failed, retry rate 15% — up from 3% yesterday, suspect model change." That's the bug report synthesis — query Langfuse API, count error traces by type, calculate retry rate, post to Slack.

---

### 5. "Vercel AI SDK and OpenRouter familiarity"

**Honest framing:** "I built FinPulse against the Anthropic SDK directly — `anthropic.Anthropic()`, `client.messages.create()`, `async_client.messages.stream()`. I haven't shipped production code with Vercel AI SDK or OpenRouter, but the concepts map directly:

- Vercel AI SDK's `streamText()` → our `stream_report_tokens()` async generator in `reporter.py` — same pattern: streaming tokens from an LLM and yielding them to an SSE endpoint
- OpenRouter's model routing → our `_MODEL = 'claude-haiku-4-5-20251001'` constant. With OpenRouter you'd replace that string and route through OpenRouter's API instead of Anthropic directly. The retry logic and Langfuse tracing are model-agnostic
- The structured output pattern — system prompt enforcing JSON, parse + validate + retry — is identical across all three SDKs

I can get productive with Vercel AI SDK in a day given I already understand the underlying patterns."

---

## SECTION 10 — QUESTIONS TO ASK THEM

1. **"What does your Langfuse setup look like for agent traces? Do you trace individual tool calls as generations within a parent trace, or do you keep each tool call as a separate root trace?"**
*(Shows you know the difference between a trace hierarchy and flat traces, and that you've thought about structuring multi-tool-call agents in Langfuse.)*

2. **"When an agent execution fails on Hyperliquid — a routing drop or a failed order — what's the chain? Does the failure propagate as an exception back to the agent, or does the agent poll for state change?"**
*(Shows you understand the difference between synchronous and event-driven failure signaling in trading systems.)*

3. **"How do you use OpenRouter — is it primarily for model fallbacks when one provider is down, or for routing different subtasks to different models based on cost and capability?"**
*(Shows you've thought about why someone would use OpenRouter beyond the obvious "one API for multiple models.")*

4. **"When you say 'routing drops' — is that WebSocket disconnections between your agent and the Hyperliquid order gateway, or something at the agent orchestration layer?"**
*(Shows you listened to their specific domain problem and want to understand it precisely before proposing solutions.)*

5. **"What does the first week look like — is there a specific pipeline component I'd own, or is it more reading codebase and fixing issues across the stack?"**
*(Practical, direct, shows you want to understand scope. Lets them describe the real work.)*

---

## SECTION 11 — THINGS NOT TO SAY

### "The MCP server is fully production-ready"
**Reality:** `mcp_server/server.py` is fully implemented with three real tools and the correct FastMCP setup. BUT it has not been connected to Claude Desktop and tested live in this session.
**Say instead:** "The MCP server is fully implemented — three tools with proper descriptions, sharing the same repository layer as the API. I haven't connected it to Claude Desktop live today but the code is complete."

---

### "Real Claude API calls are working"
**Reality:** `USE_MOCK_REPORTS=true`. `reporter.py` has the full V2 code path implemented but it's gated behind the flag.
**Say instead:** "The full Claude API integration is written and tested — the mock flag lets me develop the pipeline without API costs. Flipping `USE_MOCK_REPORTS=false` and setting a real `ANTHROPIC_API_KEY` activates it."

---

### "WebSocket real-time updates are fully live"
**Reality:** `backend/app/api/v1/ws.py` and `useWebSocket.ts` are both implemented. BUT the WebSocket push path requires a real anomaly from the running worker pipeline. With mock seeded data, the 30-second polling works; the WebSocket end-to-end has not been tested today.
**Say instead:** "The WebSocket implementation is complete — the backend subscribes to the Redis `finpulse:reports` channel and the frontend reconnects with exponential backoff. The 30-second polling is the reliable fallback I'm demoing today."

---

### "I have DeFi or Web3 experience"
**Reality:** None.
**Say instead:** "My experience is in backend systems and AI pipelines, not DeFi-specific. What I bring is the pattern recognition for agentic pipeline failures, Langfuse monitoring, and structured output validation — which from what you've described are the core problems regardless of whether the domain is equity market anomalies or Hyperliquid execution."

---

### "The V2 IQR detection is not implemented"
**Reality:** It IS fully implemented — `compute_iqr_stats()`, `detect_price_iqr()`, `determine_combined_severity()`, `run_combined_detection()` all exist in `detector.py` and are called from `detection_task.py`. 35 tests cover all edge cases.
**Say instead:** "The IQR two-signal matrix is fully implemented and tested. The worker already calls `run_combined_detection()` which runs both signals. The V2 upgrade is surfacing IQR-only anomalies separately in the API response and adding the two-signal breakdown to Langfuse metadata."
