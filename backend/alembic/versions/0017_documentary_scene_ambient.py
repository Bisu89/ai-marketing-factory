"""documentary_scene.ambient (optional particle overlay: rain|snow|wind|embers).

Revision ID: 0017_documentary_scene_ambient
Revises: 0016_documentary_export
Create Date: 2026-10-15

New nullable column for the optional scene-level ambient overlay (see
docs/documentary/PORTING_NOTES.md part C). Guarded exactly like 0015's
`assigned_hash` backfill: a no-op on any database that already has it via
create_all().
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_documentary_scene_ambient"
down_revision: str | None = "0016_documentary_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "documentary_scene" not in insp.get_table_names():
        return
    if "ambient" not in {c["name"] for c in insp.get_columns("documentary_scene")}:
        op.add_column("documentary_scene", sa.Column("ambient", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("documentary_scene", "ambient")
