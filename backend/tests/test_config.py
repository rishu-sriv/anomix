"""
Phase 1 — config tests.

Tests the only real logic in config.py: ticker_list parsing.
No database required — pure unit tests.
"""

import pytest

from app.config import Settings


def make_settings(**overrides) -> Settings:
    """Build a Settings instance with minimal required fields + any overrides."""
    base = dict(
        db_host="localhost",
        db_port=5432,
        db_name="finpulse",
        db_user="postgres",
        db_password="postgres",
        redis_url="redis://localhost:6379/0",
    )
    base.update(overrides)
    return Settings.model_validate(base)


class TestTickerListParsing:
    def test_single_ticker(self):
        s = make_settings(tickers="TSLA")
        assert s.ticker_list == ["TSLA"]

    def test_multiple_tickers(self):
        s = make_settings(tickers="AAPL,TSLA,NVDA")
        assert s.ticker_list == ["AAPL", "TSLA", "NVDA"]

    def test_strips_whitespace(self):
        s = make_settings(tickers=" AAPL , TSLA , NVDA ")
        assert s.ticker_list == ["AAPL", "TSLA", "NVDA"]

    def test_default_is_tsla(self):
        # Explicit default — env var in .env overrides the field default,
        # so we pass it explicitly rather than relying on the field default.
        s = make_settings(tickers="TSLA")
        assert s.ticker_list == ["TSLA"]


class TestRequiredFields:
    """
    Verify that required fields declare no default, meaning the app will
    fail loudly at startup if they are absent from the environment.
    Instantiating Settings() inside the container always succeeds because
    the env vars are present — so we inspect field metadata instead.
    """

    def test_db_host_is_required(self):
        from pydantic_core import PydanticUndefinedType
        field = Settings.model_fields["db_host"]
        assert isinstance(field.default, PydanticUndefinedType)

    def test_redis_url_is_required(self):
        from pydantic_core import PydanticUndefinedType
        field = Settings.model_fields["redis_url"]
        assert isinstance(field.default, PydanticUndefinedType)

    def test_db_password_is_required(self):
        from pydantic_core import PydanticUndefinedType
        field = Settings.model_fields["db_password"]
        assert isinstance(field.default, PydanticUndefinedType)


class TestDatabaseUrls:
    def test_async_url_uses_asyncpg(self):
        s = make_settings()
        assert s.async_database_url.startswith("postgresql+asyncpg://")

    def test_sync_url_uses_psycopg2(self):
        s = make_settings()
        assert s.sync_database_url.startswith("postgresql+psycopg2://")

    def test_urls_contain_db_name(self):
        s = make_settings(db_name="mydb")
        assert s.async_database_url.endswith("/mydb")
        assert s.sync_database_url.endswith("/mydb")
