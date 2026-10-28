"""owned_channel + channel_sync_run + channel_metric_daily (Channels menu).

Revision ID: 0018_owned_channels
Revises: 0017_documentary_scene_ambient
Create Date: 2026-10-28

Guarded per table: a no-op for any table create_all() already made.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_owned_channels"
down_revision: str | None = "0017_documentary_scene_ambient"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "owned_channel" not in existing:
        op.create_table(
            "owned_channel",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("platform", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("external_id", sa.String(), nullable=False),
            sa.Column("credential", sa.Text(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sync_status", sa.String(), nullable=True),
            sa.Column("last_sync_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("platform", "external_id", name="uq_owned_channel_platform_ext"),
        )
    if "channel_sync_run" not in existing:
        op.create_table(
            "channel_sync_run",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("owned_channel.id", ondelete="CASCADE"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
        )
        op.create_index("ix_channel_sync_run_channel_id", "channel_sync_run", ["channel_id"])
    if "channel_metric_daily" not in existing:
        op.create_table(
            "channel_metric_daily",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel_id", sa.Integer(), sa.ForeignKey("owned_channel.id", ondelete="CASCADE"), nullable=False),
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("followers", sa.Integer(), nullable=True),
            sa.Column("total_views", sa.Integer(), nullable=True),
            sa.Column("video_count", sa.Integer(), nullable=True),
            sa.UniqueConstraint("channel_id", "day", name="uq_channel_metric_day"),
        )
        op.create_index("ix_channel_metric_daily_channel_id", "channel_metric_daily", ["channel_id"])


def downgrade() -> None:
    op.drop_table("channel_metric_daily")
    op.drop_table("channel_sync_run")
    op.drop_table("owned_channel")
