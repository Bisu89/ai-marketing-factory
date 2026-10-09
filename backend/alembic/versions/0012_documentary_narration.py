"""Documentary narration segments + usage ledger (feature 166).

Revision ID: 0012_documentary_narration
Revises: 0011_documentary_storyboard_assets
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): create_all() makes new tables on
startup; this upgrade() also guards the one added column
(documentary_scene_counter.next_segment) for an already-migrated dev DB.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_documentary_narration"
down_revision: str | None = "0011_documentary_storyboard_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    existing = insp.get_table_names()
    if "documentary_scene_counter" in existing:
        cols = {c["name"] for c in insp.get_columns("documentary_scene_counter")}
        if "next_segment" not in cols:
            op.add_column(
                "documentary_scene_counter",
                sa.Column("next_segment", sa.Integer(), nullable=False, server_default="1"),
            )
    if "documentary_narration_segment" not in existing:
        op.create_table(
            "documentary_narration_segment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("segment_key", sa.String(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("text_hash", sa.String(), nullable=False),
            sa.Column("scene_keys", sa.JSON(), nullable=False),
            sa.Column("cache_key", sa.String(), nullable=True),
            sa.Column("audio_path", sa.String(), nullable=True),
            sa.Column("duration_sec", sa.Float(), nullable=True),
            sa.Column("chars", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("voice", sa.String(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("word_stamps", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("attempt_key", sa.String(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("master_start", sa.Float(), nullable=True),
            sa.Column("master_end", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "segment_key"),
        )
        op.create_index("ix_documentary_narration_segment_project_id", "documentary_narration_segment", ["project_id"])
    if "documentary_usage" not in existing:
        op.create_table(
            "documentary_usage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("ref", sa.String(), nullable=True),
            sa.Column("chars", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("ok", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_documentary_usage_project_id", "documentary_usage", ["project_id"])


def downgrade() -> None:
    op.drop_table("documentary_usage")
    op.drop_table("documentary_narration_segment")
    with op.batch_alter_table("documentary_scene_counter") as batch:
        batch.drop_column("next_segment")
