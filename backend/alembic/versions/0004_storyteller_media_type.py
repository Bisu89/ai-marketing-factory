"""storyteller -- add StorytellerAsset.media_type (image | video), so a
background/avatar clip can be a still image, not just a video loop.

Revision ID: 0004_storyteller_media_type
Revises: 0003_storyteller
Create Date: 2026-09-18

Additive column with a server_default -- ALTER-only, per this repo's own
migration-authoring rule (see 0003's own note on why create_all() can beat
an upgrade() to a genuinely new table; a new COLUMN on an existing table
has no such race since create_all() never adds columns to a table it
didn't create).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_storyteller_media_type"
down_revision: str | None = "0003_storyteller"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("storyteller_asset")}
    if "media_type" not in columns:
        op.add_column(
            "storyteller_asset",
            sa.Column("media_type", sa.String(), nullable=False, server_default="video"),
        )


def downgrade() -> None:
    op.drop_column("storyteller_asset", "media_type")
