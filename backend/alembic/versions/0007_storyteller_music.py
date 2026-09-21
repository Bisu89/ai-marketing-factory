"""storyteller -- optional background music, ducked under narration.

Revision ID: 0007_storyteller_music
Revises: 0006_storyteller_slideshow
Create Date: 2026-09-21

Additive column, nullable -- ALTER-only, same safe shape as 0004/0005/0006.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_storyteller_music"
down_revision: str | None = "0006_storyteller_slideshow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("storyteller_episode")}
    if "music_asset_id" not in existing:
        op.add_column("storyteller_episode", sa.Column("music_asset_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("storyteller_episode", "music_asset_id")
