from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings — builds sync_database_url from env vars
from app.config import settings

# Import all models so autogenerate picks them up.
# This import MUST be present; without it Alembic sees an empty metadata
# and will generate a migration that drops all your tables.
from app.models import Base  # noqa: F401

config = context.config

# Override sqlalchemy.url with the value derived from our pydantic settings.
# This is intentional: alembic.ini intentionally stores a placeholder URL
# so no real credentials are committed.  The real URL is built at runtime.
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (used for SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
