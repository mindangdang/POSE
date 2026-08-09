from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from alembic.operations import ops
from sqlalchemy import engine_from_config, pool

from project.backend.app.db.base import Base
import project.backend.app.db.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "ALEMBIC_DATABASE_URL is required. NEON_DB_URL is deliberately not "
            "used, to prevent accidental production migrations."
        )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _include_object(object_, name, type_, reflected, compare_to):
    # Autogenerate must never suggest deleting objects that exist only in the
    # database. Destructive changes must always be written and reviewed by hand.
    if reflected and compare_to is None:
        return False
    return True


def _reject_destructive_autogenerate(context_, revision, directives) -> None:
    if not getattr(config.cmd_opts, "autogenerate", False):
        return

    destructive_types = (ops.DropTableOp, ops.DropColumnOp)

    def contains_destructive(operation) -> bool:
        if isinstance(operation, destructive_types):
            return True
        return any(contains_destructive(child) for child in getattr(operation, "ops", ()))

    script = directives[0]
    if contains_destructive(script.upgrade_ops):
        raise RuntimeError(
            "Destructive migration detected. Write it manually and require an "
            "explicit production review."
        )


def _configure(connection=None, url=None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        include_object=_include_object,
        process_revision_directives=_reject_destructive_autogenerate,
        compare_type=True,
        compare_server_default=True,
        transactional_ddl=True,
    )


def run_migrations_offline() -> None:
    _configure(url=_database_url())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
