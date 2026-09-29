"""manhua fetch log -- feature 154, the in-app "paste a link" fetch form.

Revision ID: 0008_manhua_fetch_log
Revises: 0007_storyteller_music
Create Date: 2026-09-29

NOTE (see app/db/schema.py::sync_schema): this upgrade() never runs in
normal operation -- Base.metadata.create_all() makes this table on startup
and a fresh/unversioned DB is stamped at head. It exists so
`alembic downgrade base && alembic upgrade head` cycles cleanly and so an
older-version DB (already past 0007) picks up the new table. A genuinely
new table, so plain create_table is correct here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_manhua_fetch_log"
down_revision: str | None = "0007_storyteller_music"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # Guarded like the column-add migrations (0004-0007): an already-migrated
    # dev DB (alembic_version already recorded) runs create_all()'s new-table
    # step *before* this upgrade(), so the table can already exist by the
    # time this runs -- only a genuinely fresh/unversioned DB (stamped, never
    # migrated) would hit a plain create_table.
    if "manhua_fetch_log" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "manhua_fetch_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("chapter_dir", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("saved", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("manhua_fetch_log")
