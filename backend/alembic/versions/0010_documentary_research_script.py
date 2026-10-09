"""Documentary research (sources/claims) + script versions (feature 164).

Revision ID: 0010_documentary_research_script
Revises: 0009_documentary
Create Date: 2026-10-09

NOTE (see app/db/schema.py::sync_schema): upgrade() never runs in normal
operation -- create_all() makes these tables on startup. Guarded like 0008.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_documentary_research_script"
down_revision: str | None = "0009_documentary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None




def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "documentary_source" not in existing:
        op.create_table(
            "documentary_source",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("url", sa.String(), nullable=True),
            sa.Column("publisher", sa.String(), nullable=True),
            sa.Column("author", sa.String(), nullable=True),
            sa.Column("published_date", sa.Date(), nullable=True),
            sa.Column("accessed_date", sa.Date(), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_documentary_source_project_id", "documentary_source", ["project_id"])
    if "documentary_claim" not in existing:
        op.create_table(
            "documentary_claim",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("uncertainty_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_documentary_claim_project_id", "documentary_claim", ["project_id"])
    if "documentary_claim_source" not in existing:
        op.create_table(
            "documentary_claim_source",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("claim_id", sa.Integer(), sa.ForeignKey("documentary_claim.id"), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("documentary_source.id"), nullable=False),
            sa.UniqueConstraint("claim_id", "source_id"),
        )
        op.create_index("ix_documentary_claim_source_claim_id", "documentary_claim_source", ["claim_id"])
        op.create_index("ix_documentary_claim_source_source_id", "documentary_claim_source", ["source_id"])
    if "documentary_script" not in existing:
        op.create_table(
            "documentary_script",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("documentary_project.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("origin", sa.String(), nullable=False),
            sa.Column("outline", sa.JSON(), nullable=False),
            sa.Column("sections", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_documentary_script_project_id", "documentary_script", ["project_id"])


def downgrade() -> None:
    op.drop_table("documentary_script")
    op.drop_table("documentary_claim_source")
    op.drop_table("documentary_claim")
    op.drop_table("documentary_source")
