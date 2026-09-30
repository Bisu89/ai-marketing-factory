"""Tests for app.db.schema.sync_schema (feature 131) -- the create_all +
Alembic catch-up/stamp bootstrap. Uses a real temp SQLite file so
`command.stamp` / `command.upgrade` actually run against it.
"""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from alembic.script import ScriptDirectory

from app.db.schema import _alembic_config, current_revision, sync_schema

# The current Alembic head -- read from the script directory rather than
# hardcoded so a new migration doesn't silently break these tests.
_HEAD_REVISION = ScriptDirectory.from_config(_alembic_config("sqlite://")).get_current_head()

_STORY_TABLES = {
    "story_channel", "episode", "story", "story_character", "story_location",
    "story_chapter", "story_scene", "story_run", "story_checkpoint",
}


class SyncSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.url = f"sqlite:///{Path(self.tmpdir.name) / 'db.sqlite'}"
        self.engine = create_engine(self.url, connect_args={"check_same_thread": False})

    def tearDown(self):
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_fresh_db_gets_every_table_and_is_stamped_at_head(self):
        sync_schema(self.engine)
        names = set(inspect(self.engine).get_table_names())
        self.assertTrue(_STORY_TABLES <= names)
        # Series was removed (docs/features/157-remove-unused-features.md).
        self.assertNotIn("series", names)
        self.assertTrue(inspect(self.engine).has_table("alembic_version"))
        self.assertEqual(current_revision(self.engine), _HEAD_REVISION)

    def test_sync_is_idempotent(self):
        sync_schema(self.engine)
        rev1 = current_revision(self.engine)
        sync_schema(self.engine)  # must not raise, must not change anything
        self.assertEqual(current_revision(self.engine), rev1)

    def test_empty_alembic_version_table_is_stamped_not_upgraded(self):
        # Real-world state: a partially-completed earlier startup left an
        # `alembic_version` TABLE with no row. create_all has already made
        # every table, so sync must stamp (not run 0001's create_table over
        # tables that now exist).
        sync_schema(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM alembic_version"))
        self.assertIsNone(current_revision(self.engine))

        sync_schema(self.engine)  # must not raise "table ... already exists"

        self.assertEqual(current_revision(self.engine), _HEAD_REVISION)
        self.assertTrue(_STORY_TABLES <= set(inspect(self.engine).get_table_names()))

    def test_pre_phase1_db_catches_up(self):
        # Simulate a DB created by an older app version: everything EXCEPT
        # the story tables, and no alembic_version.
        sync_schema(self.engine)
        with self.engine.begin() as conn:
            for t in _STORY_TABLES:
                conn.execute(text(f"DROP TABLE {t}"))
            conn.execute(text("DROP TABLE alembic_version"))

        sync_schema(self.engine)  # catch-up

        names = set(inspect(self.engine).get_table_names())
        self.assertTrue(_STORY_TABLES <= names)
        self.assertEqual(current_revision(self.engine), _HEAD_REVISION)

    def test_downgrade_then_upgrade_round_trips(self):
        sync_schema(self.engine)
        cfg = _alembic_config(self.url)
        from alembic import command

        command.downgrade(cfg, "base")
        self.assertNotIn("story_scene", inspect(self.engine).get_table_names())

        command.upgrade(cfg, "head")
        self.assertIn("story_scene", inspect(self.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
