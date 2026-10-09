"""Documentary alignment, timeline and subtitles (feature 167).

Revision ID: 0013_documentary_timeline
Revises: 0012_documentary_narration
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): upgrade() never runs in normal
operation -- create_all() makes these tables on startup. Guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_documentary_timeline"
down_revision: str | None = "0012_documentary_narration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _project_fk() -> sa.ForeignKey:
    return sa.ForeignKey("documentary_project.id")


def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "documentary_segment_alignment" not in existing:
        op.create_table(
            "documentary_segment_alignment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), _project_fk(), nullable=False),
            sa.Column("segment_key", sa.String(), nullable=False),
            sa.Column("cache_key", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("coverage", sa.Float(), nullable=False),
            sa.Column("words", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "segment_key"),
        )
        op.create_index("ix_documentary_segment_alignment_project_id", "documentary_segment_alignment", ["project_id"])
    if "documentary_timing_override" not in existing:
        op.create_table(
            "documentary_timing_override",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), _project_fk(), nullable=False),
            sa.Column("scene_key", sa.String(), nullable=False),
            sa.Column("segment_cache_key", sa.String(), nullable=False),
            sa.Column("local_start", sa.Float(), nullable=False),
            sa.UniqueConstraint("project_id", "scene_key"),
        )
        op.create_index("ix_documentary_timing_override_project_id", "documentary_timing_override", ["project_id"])
    if "documentary_scene_timing" not in existing:
        op.create_table(
            "documentary_scene_timing",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), _project_fk(), nullable=False),
            sa.Column("scene_key", sa.String(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("start", sa.Float(), nullable=False),
            sa.Column("end", sa.Float(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("coverage", sa.Float(), nullable=False),
            sa.Column("needs_review", sa.Boolean(), nullable=False),
            sa.Column("master_hash", sa.String(), nullable=False),
            sa.Column("words", sa.JSON(), nullable=False),
            sa.UniqueConstraint("project_id", "scene_key"),
        )
        op.create_index("ix_documentary_scene_timing_project_id", "documentary_scene_timing", ["project_id"])
    if "documentary_subtitle" not in existing:
        op.create_table(
            "documentary_subtitle",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), _project_fk(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("start", sa.Float(), nullable=False),
            sa.Column("end", sa.Float(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("scene_key", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=False),
        )
        op.create_index("ix_documentary_subtitle_project_id", "documentary_subtitle", ["project_id"])


def downgrade() -> None:
    op.drop_table("documentary_subtitle")
    op.drop_table("documentary_scene_timing")
    op.drop_table("documentary_timing_override")
    op.drop_table("documentary_segment_alignment")
