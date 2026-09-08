"""viral source radar -- discovery_search / discovery_result.

Revision ID: 0002_viral_source_radar
Revises: 0001_storytelling_studio_phase1
Create Date: 2026-09-08

NOTE (see app/db/schema.py::sync_schema): this upgrade() never runs in
normal operation -- `Base.metadata.create_all()` makes these tables on
startup and a fresh/unversioned DB is stamped at head. It exists so
`alembic downgrade base && alembic upgrade head` cycles cleanly and so an
older-version DB (already past 0001) picks up the two new tables. Both are
genuinely new tables, so plain create_table is correct here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_viral_source_radar"
down_revision: str | None = "0001_storytelling_studio_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovery_search",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("normalized_query", sa.String(), nullable=False),
        sa.Column("expanded_queries_json", sa.Text(), nullable=True),
        sa.Column("engine_statuses_json", sa.Text(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_discovery_search_created", "discovery_search", ["created_at"])

    op.create_table(
        "discovery_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_id", sa.Integer(), sa.ForeignKey("discovery_search.id"), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.String(), nullable=True),
        sa.Column("creator_name", sa.String(), nullable=True),
        sa.Column("creator_url", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("content_tags_json", sa.Text(), nullable=True),
        sa.Column("also_on_json", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("engagement_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recency_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("short_form_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("content_signal_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("viral_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rights_status", sa.String(), nullable=False, server_default="UNKNOWN"),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("download_capability", sa.String(), nullable=False, server_default="PERMISSION_REQUIRED"),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("saved_video_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("collection", sa.String(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_discovery_result_search", "discovery_result", ["search_id"])
    op.create_index("ix_discovery_result_platform", "discovery_result", ["platform"])
    op.create_index("ix_discovery_result_viral", "discovery_result", ["viral_score"])
    op.create_index("ix_discovery_result_saved", "discovery_result", ["saved_at"])


def downgrade() -> None:
    op.drop_table("discovery_result")
    op.drop_index("ix_discovery_search_created", table_name="discovery_search")
    op.drop_table("discovery_search")
