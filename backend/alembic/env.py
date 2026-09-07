"""Alembic environment (feature 131 -- see docs/features/131-*).

This project keeps `Base.metadata.create_all()` in `app/main.py`'s
lifespan as the authority for what a *fresh* schema looks like. Alembic is
the catch-up + rollback mechanism for databases created by an OLDER
version of the app (see `app/db/schema.py::sync_schema`). Consequently
every migration from the first one onward is written ALTER-only where it
touches a pre-existing table -- `create_table` for a brand-new table is
fine (a fresh DB is stamped, never migrated, so it never runs), but a
migration must never assume `create_all` didn't already add a column.

`render_as_batch=True` -- SQLite can't `ALTER TABLE ... ALTER COLUMN` /
`DROP COLUMN`, so Alembic emulates it via table copy. `compare_type=True`
so autogenerate notices column-type changes.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Load every model onto Base.metadata (see the module docstring there).
from app.core.config import get_settings
from app.db.all_models import Base

config = context.config

# Point Alembic at the app's own configured database, not alembic.ini's
# placeholder -- unless a URL was already set programmatically by
# app.db.schema._alembic_config (which passes the URL of the engine it
# was handed, so a test or a non-default engine stays consistent).
if not (config.get_main_option("sqlalchemy.url") or "").strip():
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001 -- logging config is best-effort, never fatal
        pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
