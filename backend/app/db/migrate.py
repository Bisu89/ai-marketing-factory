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
    # Task 26 -- see docs/features/52-final-composer.md. The Final Composer's
    # own Audio Master/Captions/watermark inputs, recorded on the RenderJob
    # that used them.
    ("video_compose_job", "audio_master_path", "VARCHAR"),
    ("video_compose_job", "captions_ass_path", "VARCHAR"),
    ("video_compose_job", "watermark_enabled", "BOOLEAN DEFAULT 0"),
    ("video_compose_job", "watermark_path", "VARCHAR"),
    ("video_compose_job", "watermark_position", "VARCHAR DEFAULT 'bottom-right'"),
    ("video_compose_job", "watermark_opacity", "FLOAT DEFAULT 1.0"),
    ("video_compose_job", "watermark_scale", "FLOAT DEFAULT 0.15"),
    ("video_compose_job", "watermark_margin_x", "INTEGER DEFAULT 24"),
    ("video_compose_job", "watermark_margin_y", "INTEGER DEFAULT 24"),
    # Task 28 -- see docs/features/54-final-qa.md. Kept separate from the
    # pre-render Quality Gate's own quality_status/quality_score (different
    # checks, neither should overwrite the other's cached outcome).
    ("factory_run", "qa_status", "VARCHAR"),
    ("factory_run", "qa_score", "INTEGER"),
    # Task 59 -- see docs/features/59-ai-image-generation.md. NULL for every
    # "library" mode run (the default), same "meaningfully absent" shape as
    # qa_status/qa_score above.
    ("factory_run", "visual_generation_image_count", "INTEGER"),
    ("factory_run", "visual_generation_cost_usd", "FLOAT"),
    # Task 12 -- see docs/features/77-affiliate-engine.md. NULL means
    # organic (the pre-existing default for every row before this task).
    ("publish_log", "affiliate_link_id", "INTEGER"),
    # Outro Card -- see docs/features/89-outro-card.md. NULL for every
    # project without an Outro configured (the pre-existing default for
    # every row before this feature, and every project with
    # config.outro.enabled=False).
    ("video_compose_job", "outro_clip_path", "VARCHAR"),
]

# (index_name, table, column) -- Base.metadata.create_all() only creates
# indexes for tables it creates from scratch; an already-existing table's
# column that later gains index=True (Task 20's BatchItem.project_id) needs
# its own explicit, idempotent CREATE INDEX here, same reasoning as
# _NEW_COLUMNS above.
_NEW_INDEXES: list[tuple[str, str, str]] = [
    ("ix_batch_item_project_id", "batch_item", "project_id"),
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

        for index_name, table, column in _NEW_INDEXES:
            if table not in table_names:
                continue  # a brand-new DB: create_all() already created this index with the table
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"))

        conn.commit()
