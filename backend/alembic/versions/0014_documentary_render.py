"""Documentary render jobs (feature 169).

Revision ID: 0014_documentary_render
Revises: 0013_documentary_timeline
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): upgrade() never runs in normal
operation -- create_all() makes this table on startup. Guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_documentary_render"
down_revision: str | None = "0013_documentary_timeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "documentary_render_job" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "documentary_render_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("output_path", sa.String(), nullable=True),
        sa.Column("log_path", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("qc", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documentary_render_job_project_id", "documentary_render_job", ["project_id"])
    op.create_index("ix_documentary_render_job_input_hash", "documentary_render_job", ["input_hash"])


def downgrade() -> None:
    op.drop_table("documentary_render_job")
