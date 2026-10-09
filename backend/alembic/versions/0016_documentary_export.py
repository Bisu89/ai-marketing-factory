"""Documentary export bundles (feature 173).

Revision ID: 0016_documentary_export
Revises: 0015_documentary_scene_assigned_hash
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): create_all() makes the table on startup; guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_documentary_export"
down_revision: str | None = "0015_documentary_scene_assigned_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "documentary_export" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "documentary_export",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
        sa.Column("render_job_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documentary_export_project_id", "documentary_export", ["project_id"])


def downgrade() -> None:
    op.drop_table("documentary_export")
