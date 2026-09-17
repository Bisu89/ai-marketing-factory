"""storyteller -- storyteller_asset / storyteller_episode.

Revision ID: 0003_storyteller
Revises: 0002_viral_source_radar
Create Date: 2026-09-17

NOTE (see app/db/schema.py::sync_schema): unlike 0001/0002's own claim
("this upgrade() never runs in normal operation"), it demonstrably DOES:
any existing (non-fresh) DB behind head runs sync_schema's create_all()
first on every startup, which creates a genuinely-new table like this
migration's own before the upgrade step gets a chance to -- create_all
doesn't know or care what revision the DB is recorded at. Confirmed as a
real startup crash ("table storyteller_asset already exists") the first
time a real existing dev DB (recorded at 0002, not freshly stamped)
upgraded past a revision that adds a table. `op.create_table` here is
therefore guarded with a has_table() check so upgrade() is idempotent
against whatever create_all() already did -- the correct general rule for
every future "genuinely new table" migration, not just this one.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_storyteller"
down_revision: str | None = "0002_viral_source_radar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_table_if_missing(name: str, *columns: sa.Column) -> None:
    bind = op.get_bind()
    if name in sa.inspect(bind).get_table_names():
        return
    op.create_table(name, *columns)


def upgrade() -> None:
    _create_table_if_missing(
        "storyteller_asset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("key_color", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    _create_table_if_missing(
        "storyteller_episode",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("script_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice", sa.String(), nullable=False, server_default="vi-VN-HoaiMyNeural"),
        sa.Column("narration_rate", sa.String(), nullable=False, server_default="+0%"),
        sa.Column("burn_captions", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("background_asset_id", sa.Integer(), nullable=True),
        sa.Column("avatar_asset_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("progress_stage", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("narration_path", sa.String(), nullable=True),
        sa.Column("captions_ass_path", sa.String(), nullable=True),
        sa.Column("output_path", sa.String(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("storyteller_episode")
    op.drop_table("storyteller_asset")
