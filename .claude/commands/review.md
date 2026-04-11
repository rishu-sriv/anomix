# /review

Review the current set of changes against FinPulse coding standards.

## What this does

Audit the staged or recently edited files and check for violations of the patterns defined in CLAUDE.md:

1. **Model compliance** — UUID PK, `created_at`/`updated_at` columns, `to_dict()` method, no `float` for money
2. **Store compliance** — extends `BaseStore`, uses `get_session()`, no manual `commit()`/`rollback()`, sets `updated_at` manually on updates
3. **Route compliance** — Pydantic request models with `Field(description=...)`, standard response shape, 404 vs 500 handling
4. **Tool compliance** — `@tool` decorator, `Annotated` params, `USE WHEN` / `RETURNS` in docstring, no business logic, Decimal → float at boundary
5. **Agent compliance** — prompts in `.txt` files only, tools scoped per worker, `OrchestrationState` used correctly
6. **General** — no dead code, no commented-out blocks, no silent exception swallowing, type hints present

Report each violation with file path, line number, and the rule it breaks.
