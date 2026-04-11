# FinPulse — CLAUDE.md

Multi-tenant FastAPI service for AI financial intelligence agents and the PulseIQ product layer.

---

## Product context

FinPulse is a financial intelligence platform. Tenants are financial firms, wealth managers, or individual investors. The core value is helping finance teams understand portfolio performance, manage risk, track financial goals, and surface actionable insights — all grounded in their actual market and transaction data.

Two modes in the UI:
- **Classic mode**: Agent cards — users chat with agents (portfolio analyst, risk analyst, market strategist, etc.)
- **PulseIQ mode** (`pulseiq.intelligence_layer: true` in tenant config): Full feed — positions, alerts, risk signals, goal tracking, outcome attribution. Gated per tenant via `GET /api/pulseiq/config → { intelligence_layer: bool }`.

The PulseIQ feed shows what financial signals were detected, what portfolio actions were taken, and whether those actions led to favorable outcomes — closing the loop between AI recommendations and real portfolio results.

---

## Core entity relationships

```
Signal (signals)
  ├── SignalOutcome (signal_outcomes)     — one per signal, CASCADE delete, computed async after settlement window
  ├── SignalNote (signal_notes)           — analyst-added notes
  └── SignalPeriodSummary                 — weekly/monthly rollup, LLM-generated

Portfolio (portfolios)
  └── Position (positions)               — one per (portfolio_id, ticker), tracks quantity and cost basis

Goals (goals)                            — one per (metric_key, period_label), tracks target vs actual
  └── attribution computed in goals_store — outcomes of confirmed signals are attributed to matching goals

Alert (alerts)                           — triggered threshold breaches (price, risk, allocation drift)
Transaction (transactions)               — buy/sell/dividend events
```

**Signal lifecycle:**
1. Bulk-upserted from market data inference via `POST /api/signals/bulk-upsert` (source: equity, fx, macro, options, etc.)
2. LLM fields (`title`, `description`, `inferred_reason`, `llm_summary`) filled async after insert
3. Analyst confirms/dismisses/edits → status: `pending → confirmed | dismissed | edited`
4. After `outcome_measure_after` date passes, outcome is computed and written to `signal_outcomes`
5. Confirmed signals with outcomes get attributed to active goals via `goals_store`

**Key non-obvious things:**
- `outcome_measure_after = signal_date + effective_settlement_days` — set at creation, drives when grading runs
- `SignalOutcome` has one-to-one with `Signal` (unique constraint on `signal_id`) — upsert, not insert
- Outcomes have both a flat baseline (5-day pre-signal) and a trend-adjusted baseline (21-day regression) — both matter for verdict
- `outcome_confidence` is reduced by confounding signals active in the same window

---

## Where things live

```
database/models/            — SQLModel table definitions
database/migrations.py      — column/index migrations (run on startup per tenant)
src/store/                  — all DB operations; PulseIqStore aggregates them all
src/api/routes/             — one file per domain; registered in src/api/app.py
src/api/middleware/auth.py  — tenant-aware authentication for incoming requests
config/settings.py          — app-level env config (not tenant-specific)
src/utils/tenant_config.py  — tenant config loader (file or Vault)
src/agents/                 — LangGraph agents
src/agents/prompts/         — all system prompts as .txt files (never inline in code)
src/tools/                  — LangChain @tool definitions by domain
src/services/               — business logic (artifact, alert, email, Slack, etc.)
src/constants/              — enums, prompt maps, config constants
src/cache/                  — Redis + external data caching layers
src/guardrails/             — input validation and safety checks
```

---

## CRUD pattern

Every entity follows the same structure. This is what keeps the codebase consistent and bug-free.

### Model — `database/models/<entity>.py`

- `SQLModel, table=True`, always `{"schema": "public"}`
- UUID PK with both `default_factory=uuid.uuid4` and `server_default=func.gen_random_uuid()`
- *(No `tenant_id` field — each tenant has its own database. Per-tenant isolation is handled at the DB level.)*
- `created_at` / `updated_at` as `TIMESTAMP(timezone=True)` with `server_default=func.now()`
- `to_dict()` method returning serialized dict — isoformat datetimes, `float()` numerics, `str()` UUIDs

```python
# Example pattern
class Portfolio(SQLModel, table=True):
    __tablename__ = "portfolios"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid.uuid4, server_default=func.gen_random_uuid(), primary_key=True)
    name: str
    currency: str = "USD"
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now()))

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "currency": self.currency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

### Store — `src/store/<entity>_store.py`

- Extends `BaseStore`
- No need to filter queries by `tenant_id` — each store instance operates on its own tenant's DB
- Use `with self.get_session() as session:` — commits on exit, rolls back on exception, never manage transactions manually
- Call `session.flush()` before `to_dict()` when you need DB-generated values after insert
- `updated_at` doesn't auto-update — set it manually: `obj.updated_at = datetime.utcnow()`
- Register the store in `PulseIqStore.__init__` (`src/store/pulseiq_store.py`) and `src/store/__init__.py`

### Route — `src/api/routes/<entity>_routes.py`

- Instantiate `PulseIqStore()` per request
- Typed Pydantic request models with `Field(description=...)` on every parameter
- Response shape: `{"status": "success", "data": rows, "count": len(rows)}` for lists; `{"status": "success", "data": {...}}` for single
- 404s raise `HTTPException(status_code=404)`, not 500; all other exceptions log + raise 500
- Register in `app.py`

### Migrations — `database/migrations.py`

Add to `run_migrations_for_tenant()`. All helpers in `database/migration_helpers.py` are idempotent (safe to re-run):
`add_column`, `drop_column`, `create_index`, `create_unique_constraint`, `drop_unique_constraint`, `drop_table`, `execute_sql`.

New tables don't need migration entries — created automatically from models on startup.

---

## Agents

Agents are LangGraph stateful graphs. Each agent has an orchestrator node that routes to domain worker nodes, which are then synthesized into a final response.

### Agent IDs

```python
AGENT_IDS = ["portfolio_analyst", "risk_analyst", "market_strategist", "trade_advisor"]

# Pipeline agents (single node, no orchestration):
_PIPELINE_AGENTS = {"market_strategist"}
```

### Agent architecture

```
User Query
  → Orchestrator Node  (LLM decides which workers to call and in what order)
  → Batch Node         (runs tasks: sequential or parallel based on dependencies)
  → Worker Nodes       (specialists: portfolio, risk, market_data, macro, alerts)
  → Synthesizer Node   (assembles worker results into a cohesive response)
  → Response (JSON or SSE)
```

### Worker domains

| Worker | Owns |
|--------|------|
| `portfolio` | Holdings, positions, performance, allocation |
| `risk` | VaR, drawdown, concentration risk, correlation |
| `market_data` | Prices, OHLCV, volume, sector data |
| `macro` | Macro indicators, yield curves, FX rates |
| `alerts` | Threshold breaches, drift events, anomalies |
| `execution` | Trade execution plans, order management |

### Prompt loading convention

All prompts live in `.txt` files — never inline in Python:

```
src/agents/prompts/<agent_id>.txt             — top-level agent system prompt
src/agents/prompts/orchestration/<name>.txt   — orchestrator routing instructions
src/agents/prompts/workers/<worker_id>.txt    — per-worker system prompt
src/agents/prompts/tasks/<name>.txt           — one-off task prompts
```

Load with:
```python
load_agent_prompt(agent_id)           # → prompts/{agent_id}.txt
load_orchestration_prompt(name)       # → prompts/orchestration/{name}.txt
load_worker_prompt(worker_id)         # → prompts/workers/{worker_id}.txt
load_task_prompt(name)                # → prompts/tasks/{name}.txt
```

---

## Skills (Tools)

Tools are LangChain `@tool`-decorated functions. Each tool has a docstring with **USE WHEN** and **RETURNS** sections. Workers are given only the tools relevant to their domain.

### Tool definition pattern

```python
from langchain_core.tools import tool
from typing import Annotated, Optional, Dict, Any
from src.utils.context import get_tenant_id

@tool
def get_portfolio_positions(
    portfolio_id: Annotated[str, "UUID of the portfolio to fetch positions for"],
    as_of_date: Annotated[Optional[str], "ISO date string; defaults to today if omitted"] = None,
) -> Dict[str, Any]:
    """
    Fetch all open positions for a portfolio as of a given date.

    USE WHEN: User asks about current holdings, position sizes, allocation breakdown,
    or wants to know what's in a portfolio.

    RETURNS: List of positions with ticker, quantity, cost_basis, current_value,
    unrealized_pnl, weight_pct.
    """
    tenant_id = get_tenant_id()
    store = PulseIqStore()
    positions = store.positions.get_by_portfolio(portfolio_id, as_of_date=as_of_date)
    return {"success": True, "data": [p.to_dict() for p in positions]}
```

### Tool categories

| File | Tools |
|------|-------|
| `portfolio_tools.py` | `get_portfolio_positions`, `get_portfolio_performance`, `get_allocation_breakdown` |
| `risk_tools.py` | `get_var_metrics`, `get_drawdown_stats`, `get_concentration_risk`, `get_correlation_matrix` |
| `market_data_tools.py` | `get_price_history`, `get_ohlcv`, `get_sector_performance` |
| `macro_tools.py` | `get_yield_curve`, `get_fx_rates`, `get_macro_indicators` |
| `signal_tools.py` | `get_signals`, `get_signal_outcomes`, `update_signal_status` |
| `alert_tools.py` | `get_active_alerts`, `acknowledge_alert`, `create_alert_rule` |
| `artifact_tool.py` | `artifact_tool(action, artifact_type)` — creates reports, PDFs, Slack messages |
| `flexible_query_tools.py` | `run_market_data_query` — custom data warehouse queries |

---

## Multi-tenancy

- One Postgres DB per tenant, managed by `database_orchestrator`
- All table and model definitions are at the tenant DB level; tenant-specific data is fully isolated by database
- Tenant config (LLM model, data sources, Keycloak, feature flags) in `tenantConfig.yml` locally, Vault in prod
- Deep merge: default config → tenant-specific config; tenant values win
- Tenant context propagated via Python `contextvars` (`set_tenant_id()` / `get_tenant_id()`) — never pass `tenant_id` through function args inside service/store/tool layers

---

## Tenant config structure

```yaml
tenantConfig:
  your-tenant-id:
    tenantName: string
    dataModel:
      dbUrl: postgresql://user:pass@host:port/db
    market_data_provider: alpaca | polygon | yfinance
    llm_config:
      default: gemini | openai | anthropic
      gemini:
        model: gemini-2.5-pro
        temperature: 0.0
    keycloakConfig:
      realmName: string
      clientId: string
      clientSecret: string
    agents: portfolio_analyst,risk_analyst,market_strategist,trade_advisor
    pulseiq:
      intelligence_layer: true
```

---

## Standards

- Follow the CRUD pattern above — no one-off implementations
- Typed Pydantic request models with `Field(description=...)` on every route parameter
- Meaningful log messages with context: `logger.error(f"[portfolio] failed to fetch positions: {e}", exc_info=True)`
- No silent exception swallowing in stores — let them bubble to the route handler
- No dead code, no commented-out blocks
- Type hints throughout (`Optional`, `Dict`, `List`, etc. from `typing`)
- Tools must be data-grounded: every claim in an agent response must come from a tool result, not LLM knowledge
- Prompts live in `.txt` files only — never inline system prompts in Python
- All financial numbers stored as `Numeric(precision, scale)` in Postgres — never `float` for money/prices
