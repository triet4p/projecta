"""Alembic environment for the connector-only PostgreSQL schema."""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context
from projecta_api.config import Settings
from projecta_api.operational.schema import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    try:
        return Settings().connector_sync_database_url()
    except ValueError as exc:
        raise RuntimeError("connector PostgreSQL configuration is incomplete") from exc


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        hide_parameters=True,
    )

    with connectable.connect() as connection:
        # One advisory lock serializes migration runners without making API
        # replicas migration owners. The lock is held for this connection.
        connection.execute(text("SELECT pg_advisory_lock(73104510)"))
        try:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
            # The advisory lock query starts a SQLAlchemy transaction before
            # Alembic enters its context. Commit explicitly so the migration
            # version and transactional DDL survive connection cleanup.
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(73104510)"))
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
