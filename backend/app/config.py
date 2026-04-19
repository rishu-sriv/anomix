from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database (TimescaleDB) ────────────────────────────────
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str

    # ── Redis ────────────────────────────────────────────────
    redis_url: str

    # ── AI (V2 only — stub values are fine for V1) ───────────
    anthropic_api_key: str = "sk-ant-stub"
    langfuse_public_key: str = "pk-lf-stub"
    langfuse_secret_key: str = "sk-lf-stub"
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── App config ───────────────────────────────────────────
    # Stored as a raw comma-separated string so pydantic-settings never
    # tries to JSON-decode it.  Use the .ticker_list property for a list.
    tickers: str = "TSLA"
    anomaly_zscore_threshold: float = 2.5
    use_mock_reports: bool = True
    backend_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def ticker_list(self) -> list[str]:
        return [t.strip() for t in self.tickers.split(",") if t.strip()]

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
