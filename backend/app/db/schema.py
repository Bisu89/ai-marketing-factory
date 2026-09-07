"""Schema bootstrap for app startup (feature 131 -- see docs/features/131-*).

The rule, in one place:

  `Base.metadata.create_all()` is the authority for what a FRESH schema
  looks like. It is idempotent -- it only ever CREATEs missing tables,
  never touches an existing one. Alembic is the catch-up + rollback
  mechanism for a database created by an OLDER version of this app.

`sync_schema(engine)` runs on every startup and does, in order:

  1. create_all()                      -- brand-new tables (a fresh DB, or
                                          a new module's tables on upgrade)
  2. run_additive_column_migrations()  -- legacy pre-Alembic column adds
                                          (frozen list; superseded by (4))
  3. if the DB has no recorded Alembic revision (no `alembic_version`
     table, or the table exists but is empty):
        alembic  stamp head            -- create_all just produced the
                                          current schema, so record it as
                                          up-to-date; migrations never run
     else:
        alembic  upgrade head          -- an older-version DB catches up
                                          via real ALTER migrations

Consequence for migration authors: every migration is ALTER-only where it
touches a table create_all already owns. `op.create_table` for a
genuinely new table is fine (a fresh DB is stamped, never migrated, so it
never runs) -- but a migration must never assume create_all didn't already
add a column.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import IS_FROZEN, get_settings, resource_path
# Importing all_models guarantees every table is on Base.metadata before
# create_all runs -- sync_schema must not depend on the caller having
# imported the right model modules first.
from app.db.all_models import Base
from app.db.migrate import run_additive_column_migrations

logger = logging.getLogger(__name__)


def _alembic_script_dir() -> Path:
    """The `alembic/` script directory. Frozen: bundled at sys._MEIPASS/
    alembic (see AIContentLibrary.spec's datas). Dev: it lives next to this
    package's own root, backend/alembic (schema.py is backend/app/db/schema.py).
    """
    if IS_FROZEN:
        return resource_path("alembic")
    return Path(__file__).resolve().parents[2] / "alembic"


def _alembic_config(db_url: str | None = None) -> Config:
    """Programmatic Alembic config -- points at the bundled `alembic/`
    script directory and a database URL, so no alembic.ini needs to ship.
    `db_url` defaults to the app's configured database; sync_schema passes
    the URL of the engine it was handed so a test (or a non-default engine)
    stays consistent.
    """
    cfg = Config()
    cfg.set_main_option("script_location", str(_alembic_script_dir()))
    cfg.set_main_option("sqlalchemy.url", db_url or get_settings().database_url)
    return cfg


def _db_has_any_app_table(engine: Engine) -> bool:
    existing = set(inspect(engine).get_table_names())
    return bool(existing & set(Base.metadata.tables.keys()))


def sync_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
    run_additive_column_migrations(engine)

    cfg = _alembic_config(str(engine.url))
    recorded = current_revision(engine)
    if recorded is None:
        # No recorded revision -- either no alembic_version table at all, or
        # the table exists but is empty (a partially-completed earlier
        # startup). create_all above just produced the current schema, so
        # stamp it as head rather than running the baseline migration's
        # create_table over tables that now exist.
        logger.info("alembic: stamping database at head (no recorded revision)")
        command.stamp(cfg, "head")
    else:
        logger.info("alembic: upgrading database to head (currently at %s)", recorded)
        command.upgrade(cfg, "head")


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
