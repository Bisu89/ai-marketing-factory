"""Documentary storyboard scenes + asset registry (feature 165).

Revision ID: 0011_documentary_storyboard_assets
Revises: 0010_documentary_research_script
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): upgrade() never runs in normal
operation -- create_all() makes these tables on startup. Guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_documentary_storyboard_assets"
down_revision: str | None = "0010_documentary_research_script"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "documentary_asset" not in existing:
        op.create_table(
            "documentary_asset",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("origin", sa.String(), nullable=False),
            sa.Column("source_url", sa.String(), nullable=True),
            sa.Column("license", sa.String(), nullable=True),
            sa.Column("attribution", sa.String(), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("input_hash", sa.String(), nullable=True),
            sa.Column("content_hash", sa.String(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("approval_status", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "content_hash"),
        )
        op.create_index("ix_documentary_asset_project_id", "documentary_asset", ["project_id"])
        op.create_index("ix_documentary_asset_input_hash", "documentary_asset", ["input_hash"])
    if "documentary_scene" not in existing:
        op.create_table(
            "documentary_scene",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("scene_key", sa.String(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("section_kind", sa.String(), nullable=False),
            sa.Column("narration_text", sa.Text(), nullable=False),
            sa.Column("narration_hash", sa.String(), nullable=False),
            sa.Column("claim_ids", sa.JSON(), nullable=False),
            sa.Column("visual_objective", sa.Text(), nullable=False),
            sa.Column("visual_preset", sa.String(), nullable=False),
            sa.Column("asset_strategy", sa.String(), nullable=False),
            sa.Column("image_group", sa.String(), nullable=True),
            sa.Column("asset_id", sa.Integer(), sa.ForeignKey("documentary_asset.id"), nullable=True),
            sa.Column("input_hash", sa.String(), nullable=True),
            sa.Column("assigned_hash", sa.String(), nullable=True),
            sa.Column("on_screen_text", sa.JSON(), nullable=False),
            sa.Column("motion_notes", sa.Text(), nullable=True),
            sa.Column("sfx_cues", sa.JSON(), nullable=False),
            sa.Column("expected_duration", sa.Float(), nullable=False),
            sa.Column("actual_duration", sa.Float(), nullable=True),
            sa.Column("render_status", sa.String(), nullable=False),
            sa.Column("user_edited", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "scene_key"),
        )
        op.create_index("ix_documentary_scene_project_id", "documentary_scene", ["project_id"])
    if "documentary_scene_counter" not in existing:
        op.create_table(
            "documentary_scene_counter",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), primary_key=True),
            sa.Column("next_scene", sa.Integer(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("documentary_scene_counter")
    op.drop_table("documentary_scene")
    op.drop_table("documentary_asset")
