"""Vox Documentary Factory -- project + approval history (feature 163).

Revision ID: 0009_documentary
Revises: 0008_manhua_fetch_log
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): upgrade() never runs in normal
operation -- create_all() makes these tables on startup. Guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_documentary"
down_revision: str | None = "0008_manhua_fetch_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "documentary_project" not in existing:
        op.create_table(
            "documentary_project",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("topic", sa.Text(), nullable=False),
            sa.Column("language", sa.String(), nullable=False),
            sa.Column("state", sa.String(), nullable=False),
            sa.Column("failed_from_state", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("budget_usd", sa.Float(), nullable=True),
            sa.Column("is_demo", sa.Boolean(), nullable=False),
            sa.Column("research_version", sa.Integer(), nullable=False),
            sa.Column("script_version", sa.Integer(), nullable=False),
            sa.Column("storyboard_version", sa.Integer(), nullable=False),
            sa.Column("narration_version", sa.Integer(), nullable=False),
            sa.Column("render_version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "documentary_approval" not in existing:
        op.create_table(
            "documentary_approval",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("gate", sa.String(), nullable=False),
            sa.Column("decision", sa.String(), nullable=False),
            sa.Column("artifact_version", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_documentary_approval_project_id", "documentary_approval", ["project_id"])


def downgrade() -> None:
    op.drop_table("documentary_approval")
    op.drop_table("documentary_project")
