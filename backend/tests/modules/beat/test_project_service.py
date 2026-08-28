"""Tests for app.modules.beat.project_service -- specifically that a
factory stage re-saving a project's BeatPlan (updated beats/timing) never
silently wipes a package override (manual_title/description/hashtags) the
user pinned via set_project_package_overrides. Same class of bug Task 21's
idea/content_brief/script_locked hit; fixed once in update_project_beat_plan.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.modules.beat.models import Project
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ProjectConfig
from app.modules.beat import project_service


class _ProjectServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmpdir.name) / 'test.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine, tables=[Project.__table__])
        self.Session = sessionmaker(bind=self.engine)
        self._patcher = patch.object(project_service, "SessionLocal", self.Session)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _project_with_beats(self) -> int:
        pid = project_service.create_project("Ep", "kịch bản mẫu", ProjectConfig())
        plan = BeatPlan(
            script_text="kịch bản mẫu",
            beats=[Beat(id="b1", order=1, type=BeatType.HOOK, narration="Câu mở.", duration=3.0)],
            project_name="Ep",
        )
        project_service.update_project_beat_plan(pid, plan)
        return pid

    def _reload_beats(self, pid: int):
        draft = project_service.get_project_draft(pid)
        return draft


class PackageOverridePreservationTests(_ProjectServiceTestCase):
    def test_beat_plan_resave_keeps_a_pinned_manual_title(self):
        pid = self._project_with_beats()
        project_service.set_project_package_overrides(pid, title="Tiêu đề tôi tự chọn")

        # A factory stage re-saves the plan with updated beat timing -- it
        # reconstructs BeatPlan(...) and never passes manual_title.
        draft = project_service.get_project_draft(pid)
        resaved = BeatPlan(
            script_text=draft.script_text,
            beats=[b.model_copy(update={"duration": 4.2, "start": 0.0, "end": 4.2}) for b in draft.beats],
            project_name=draft.project_name,
            config=draft.config,
        )
        project_service.update_project_beat_plan(pid, resaved)

        after = project_service.get_project_draft(pid)
        self.assertEqual(after.manual_title, "Tiêu đề tôi tự chọn")
        self.assertEqual(after.beats[0].duration, 4.2)

    def test_all_three_overrides_are_preserved(self):
        pid = self._project_with_beats()
        project_service.set_project_package_overrides(
            pid, title="T", description="Mô tả", hashtags=["#a", "#b"]
        )
        draft = project_service.get_project_draft(pid)
        project_service.update_project_beat_plan(
            pid,
            BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name),
        )
        after = project_service.get_project_draft(pid)
        self.assertEqual(after.manual_title, "T")
        self.assertEqual(after.manual_description, "Mô tả")
        self.assertEqual(after.manual_hashtags, ["#a", "#b"])

    def test_an_explicit_incoming_override_still_wins(self):
        pid = self._project_with_beats()
        project_service.set_project_package_overrides(pid, title="Cũ")
        draft = project_service.get_project_draft(pid)
        project_service.update_project_beat_plan(
            pid,
            BeatPlan(
                script_text=draft.script_text, beats=draft.beats,
                project_name=draft.project_name, manual_title="Mới",
            ),
        )
        self.assertEqual(project_service.get_project_draft(pid).manual_title, "Mới")

    def test_no_override_set_stays_none(self):
        pid = self._project_with_beats()
        draft = project_service.get_project_draft(pid)
        project_service.update_project_beat_plan(
            pid,
            BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name),
        )
        self.assertIsNone(project_service.get_project_draft(pid).manual_title)


if __name__ == "__main__":
    unittest.main()
