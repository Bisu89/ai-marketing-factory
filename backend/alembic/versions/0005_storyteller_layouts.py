"""storyteller -- layout templates: triptych split-screen + disclaimer /
story-info overlays.

Revision ID: 0005_storyteller_layouts
Revises: 0004_storyteller_media_type
Create Date: 2026-09-18

All additive columns with server_default/nullable -- ALTER-only, same safe
shape as 0004 (create_all() never alters a table it didn't create, so this
has none of 0003's create_table race).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_storyteller_layouts"
down_revision: str | None = "0004_storyteller_media_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_COLUMNS = (
    ("layout", sa.String(), {"server_default": "single"}),
    ("left_asset_id", sa.Integer(), {}),
    ("middle_asset_id", sa.Integer(), {}),
    ("right_asset_id", sa.Integer(), {}),
    ("disclaimer_text", sa.String(), {}),
    ("story_title", sa.String(), {}),
    ("story_author", sa.String(), {}),
    ("story_character", sa.String(), {}),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("storyteller_episode")}
    for name, col_type, kwargs in _NEW_COLUMNS:
        if name not in existing:
            nullable = "server_default" not in kwargs
            op.add_column("storyteller_episode", sa.Column(name, col_type, nullable=nullable, **kwargs))


def downgrade() -> None:
    for name, _col_type, _kwargs in reversed(_NEW_COLUMNS):
        op.drop_column("storyteller_episode", name)
