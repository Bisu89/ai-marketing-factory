"""storyteller -- slideshow layout: many ordered images (one script beat +
random Ken Burns zoom per image) instead of a single background/triptych
panel.

Revision ID: 0006_storyteller_slideshow
Revises: 0005_storyteller_layouts
Create Date: 2026-09-17

Additive column, nullable, no server_default needed (NULL == no slides) --
ALTER-only, same safe shape as 0004/0005.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_storyteller_slideshow"
down_revision: str | None = "0005_storyteller_layouts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("storyteller_episode")}
    if "slide_asset_ids" not in existing:
        op.add_column("storyteller_episode", sa.Column("slide_asset_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("storyteller_episode", "slide_asset_ids")
