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
