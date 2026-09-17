"""storyteller -- storyteller_asset / storyteller_episode.

Revision ID: 0003_storyteller
Revises: 0002_viral_source_radar
Create Date: 2026-09-17

NOTE (see app/db/schema.py::sync_schema): this upgrade() never runs in
normal operation -- create_all() makes these tables on startup and a
fresh/unversioned DB is stamped at head. Exists so
`alembic downgrade base && alembic upgrade head` cycles cleanly and so an
older-version DB catches up. Both are genuinely new tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_storyteller"
down_revision: str | None = "0002_viral_source_radar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
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

    op.create_table(
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
