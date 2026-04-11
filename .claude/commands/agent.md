# /agent

Scaffold a new LangGraph agent for FinPulse.

## Usage

`/new-agent <agent_id> <worker1,worker2,...>`

Example: `/new-agent risk_analyst portfolio,market_data,macro`

## What this does

1. **`src/agents/prompts/<agent_id>.txt`** — top-level system prompt stub
2. **`src/agents/prompts/orchestration/orchestrator_<agent_id>.txt`** — orchestrator routing rules stub (include domain table: which worker owns which question types)
3. **`src/agents/prompts/workers/<worker>.txt`** for each listed worker — worker system prompt stub
4. **`src/agents/<agent_id>.py`** — LangGraph graph definition with orchestrator → batch → worker → synthesizer flow
5. Register the agent ID in `src/agents/factory.py` under `AGENT_IDS`

## Agent conventions

- Orchestrator uses structured output to produce a `Batch` (list of tasks with `worker`, `query`, `execution: sequential|parallel`)
- Workers receive only their domain-specific tools — never give a worker tools outside its domain
- Synthesizer assembles all `completed_batches` results into a single cohesive response
- State type is `OrchestrationState` — never add raw dict fields, always extend the TypedDict
- Pipeline agents (no orchestration, single node) go in `_PIPELINE_AGENTS` set
