# FinPulse Makefile
# All commands run from the project root.
# Usage: make <target>

COMPOSE = docker compose -f infra/docker-compose.yml
BACKEND = $(COMPOSE) exec backend
DB      = $(COMPOSE) exec timescaledb

.PHONY: dev build down logs test test-backend test-frontend migrate migration lint shell db redis-cli help

# ─── Core ────────────────────────────────────────────────────

dev:
	$(COMPOSE) up -d --build

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
