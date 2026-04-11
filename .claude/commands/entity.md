# /entity

Scaffold a new CRUD entity for FinPulse following the project conventions.

## Usage

`/new-entity <EntityName>`

## What this does

Given an entity name (e.g. `Portfolio`, `Position`, `Alert`), create the following files following the patterns in CLAUDE.md:

1. **`database/models/<entity_snake>.py`** — SQLModel with UUID PK, `created_at`/`updated_at`, and `to_dict()`
2. **`src/store/<entity_snake>_store.py`** — extends `BaseStore`, uses `get_session()` context manager
3. **`src/api/routes/<entity_snake>_routes.py`** — FastAPI router with GET list, GET by ID, POST create, PATCH update, DELETE endpoints; typed Pydantic request models; standard response shape
4. Register the store in `src/store/pulseiq_store.py` and `src/store/__init__.py`
5. Register the router in `src/api/app.py`

## Conventions to follow

- No `tenant_id` field on models — isolation is at DB level
- `updated_at` must be set manually on updates: `obj.updated_at = datetime.utcnow()`
- Call `session.flush()` before `to_dict()` after inserts
- 404 raises `HTTPException(status_code=404)`, everything else logs and raises 500
- All financial numeric fields use `Numeric` column type, not `float`
