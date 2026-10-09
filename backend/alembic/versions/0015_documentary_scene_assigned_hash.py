"""Backfill documentary_scene.assigned_hash on databases created mid-development.

Revision ID: 0015_documentary_scene_assigned_hash
Revises: 0014_documentary_render
Create Date: 2026-10-09

`assigned_hash` was added to 0011's create_table after some dev databases had already been
built from an interim model by create_all() and stamped at head, so 0011 never ran for them and
the column was missing (POST /storyboard/plan -> HTTP 500). Guarded: a no-op wherever the
column already exists, which is every database built from the final 0011.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_documentary_scene_assigned_hash"
down_revision: str | None = "0014_documentary_render"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "documentary_scene" not in insp.get_table_names():
        return
    if "assigned_hash" not in {c["name"] for c in insp.get_columns("documentary_scene")}:
        op.add_column("documentary_scene", sa.Column("assigned_hash", sa.String(), nullable=True))


def downgrade() -> None:
    # 0011 defines this column, so the schema at 0014 already contains it: nothing to undo.
    pass
