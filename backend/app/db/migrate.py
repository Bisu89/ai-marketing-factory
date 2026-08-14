"""Additive-only column migrations for tables that already existed before a
new column was added to their ORM model. Base.metadata.create_all() (see
main.py's lifespan) only creates *missing tables* -- it never alters an
existing table's columns, so a table that predates a schema change (like
`asset`, extended in Task 15 -- see docs/features/41-local-asset-ingestion.md)
needs one explicit, idempotent ALTER TABLE per new column the first time
the app starts against an old database. Every real user's dev database
already has rows in `asset` from before this change, so this must never
drop/recreate the table -- same "additive-only, no migration framework"
convention already used for brand-new tables throughout this app, just
extended to column-level for the first time here.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (table, column, SQL type) -- add here whenever a column is added to an
# already-shipped table's model instead of a brand-new one.
_NEW_COLUMNS: list[tuple[str, str, str]] = [
    ("asset", "content_hash", "VARCHAR"),
    ("asset", "orientation", "VARCHAR"),
    ("asset", "category", "VARCHAR"),
    ("asset", "emotion", "VARCHAR"),
    ("asset", "status", "VARCHAR"),
    ("asset", "thumbnail_path", "VARCHAR"),
    # Task 19 -- see docs/features/45-factory-reliability.md. DEFAULT 1 (not
    # bare INTEGER) so existing rows backfill to a real attempt count
    # instead of NULL -- the ORM model declares this column NOT NULL.
    ("factory_run", "attempt", "INTEGER DEFAULT 1"),
]


def run_additive_column_migrations(engine: Engine) -> None:
    with engine.connect() as conn:
        table_names = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        for table, column, sql_type in _NEW_COLUMNS:
            if table not in table_names:
                continue  # a brand-new DB: create_all() already created this table with every current column
            existing_columns = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            if column not in existing_columns:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
        conn.commit()
