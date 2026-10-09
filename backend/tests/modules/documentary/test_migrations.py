"""Migrations and models must describe the same schema. A column added to a model (or to an
unreleased migration) but missing from the migration chain only shows up on real databases --
as it once did (documentary_scene.assigned_hash -> HTTP 500)."""

import os
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

import app.db.all_models  # noqa: F401  (loads every model onto Base.metadata)
from app.core.config import get_settings
from app.db.base import Base

BACKEND = Path(__file__).resolve().parents[3]


class DocumentarySchemaDriftTests(unittest.TestCase):
    def test_migrated_schema_matches_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp, 'm.db').as_posix()}"
            old = os.environ.get("APP_DATABASE_URL")
            os.environ["APP_DATABASE_URL"] = url
            get_settings.cache_clear()
            engine = None
            try:
                cfg = Config(str(BACKEND / "alembic.ini"))
                cfg.set_main_option("script_location", str(BACKEND / "alembic"))
                command.upgrade(cfg, "head")
                engine = sa.create_engine(url)
                insp = sa.inspect(engine)
                problems = []
                for name, table in Base.metadata.tables.items():
                    if not name.startswith("documentary_"):
                        continue
                    if name not in insp.get_table_names():
                        problems.append(f"{name}: table missing from migrations")
                        continue
                    have = {c["name"] for c in insp.get_columns(name)}
                    want = {c.name for c in table.columns}
                    if have != want:
                        problems.append(f"{name}: missing {sorted(want - have)}, extra {sorted(have - want)}")
                self.assertEqual(problems, [])
            finally:
                if engine is not None:
                    engine.dispose()
                if old is None:
                    os.environ.pop("APP_DATABASE_URL", None)
                else:
                    os.environ["APP_DATABASE_URL"] = old
                get_settings.cache_clear()

    def test_backfill_migration_adds_the_missing_column_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp, 'b.db').as_posix()}"
            engine = sa.create_engine(url)
            try:
                with engine.begin() as conn:
                    conn.execute(sa.text("create table documentary_scene (id integer primary key, scene_key varchar)"))
                    from alembic.migration import MigrationContext
                    from alembic.operations import Operations

                    ctx = MigrationContext.configure(conn)
                    with Operations.context(ctx):
                        import runpy

                        ns = runpy.run_path(str(BACKEND / "alembic" / "versions" / "0015_documentary_scene_assigned_hash.py"))
                        ns["upgrade"]()
                        ns["upgrade"]()  # second run must be a no-op, not an error
                cols = {c["name"] for c in sa.inspect(engine).get_columns("documentary_scene")}
                self.assertIn("assigned_hash", cols)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
