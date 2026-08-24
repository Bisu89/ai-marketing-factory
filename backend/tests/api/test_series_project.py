"""Tests for the Series<->Project composition root
(app/api/v1/endpoints/series_project.py) -- real app.modules.series.Series
and app.modules.beat.Project sharing one in-memory database, route handlers
called directly as plain functions (this codebase's established convention,
see tests/api/test_batch_render.py's own docstring).
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.series_project import AttachSeriesRequest, attach_project_to_series, list_series_projects
from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.modules.beat.models import Project
from app.modules.beat.project_service import create_project
from app.modules.beat.schemas import ProjectConfig
from app.modules.series.models import Series
from app.modules.series.service import create_series


class _SeriesProjectTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=[Series.__table__, Project.__table__])
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patchers = [
            patch("app.modules.series.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.series_project.SessionLocal", self.TestSessionLocal),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.engine.dispose()

    def _make_project(self, name: str, style_prompt: str = "") -> int:
        config = ProjectConfig()
        config = config.model_copy(update={
            "visual_generation": config.visual_generation.model_copy(update={"image_style_prompt": style_prompt}),
        })
        return create_project(name, "A short test script.", config)


class AttachProjectToSeriesTests(_SeriesProjectTestCase):
    def test_first_episode_gets_episode_number_one(self):
        series = create_series("My Series", "male, 28, grey hoodie")
        project_id = self._make_project("Episode 1")

        result = attach_project_to_series(project_id, AttachSeriesRequest(series_id=series.id))

        self.assertEqual(result.series_id, series.id)
        self.assertEqual(result.episode_number, 1)

    def test_second_episode_in_same_series_gets_episode_number_two(self):
        series = create_series("My Series", "male, 28, grey hoodie")
        first_id = self._make_project("Episode 1")
        second_id = self._make_project("Episode 2")

        attach_project_to_series(first_id, AttachSeriesRequest(series_id=series.id))
        second = attach_project_to_series(second_id, AttachSeriesRequest(series_id=series.id))

        self.assertEqual(second.episode_number, 2)

    def test_character_description_is_appended_to_image_style_prompt(self):
        series = create_series("My Series", "male, 28, short messy hair, grey hoodie")
        project_id = self._make_project("Episode 1", style_prompt="cinematic realistic photography")

        result = attach_project_to_series(project_id, AttachSeriesRequest(series_id=series.id))

        style = result.config.visual_generation.image_style_prompt
        self.assertIn("cinematic realistic photography", style)
        self.assertIn("male, 28, short messy hair, grey hoodie", style)

    def test_attaching_one_project_does_not_touch_another_projects_config(self):
        series = create_series("My Series", "male, 28, grey hoodie")
        attached_id = self._make_project("Episode 1")
        untouched_id = self._make_project("Untouched", style_prompt="original style")

        attach_project_to_series(attached_id, AttachSeriesRequest(series_id=series.id))

        from app.modules.beat.project_service import get_project_draft

        untouched = get_project_draft(untouched_id)
        self.assertEqual(untouched.config.visual_generation.image_style_prompt, "original style")
        self.assertIsNone(untouched.series_id)

    def test_editing_series_description_later_does_not_retroactively_change_attached_project(self):
        series = create_series("My Series", "original description")
        project_id = self._make_project("Episode 1")
        attach_project_to_series(project_id, AttachSeriesRequest(series_id=series.id))

        from app.modules.series.service import update_series

        update_series(series.id, "My Series", "a completely different description")

        from app.modules.beat.project_service import get_project_draft

        project = get_project_draft(project_id)
        self.assertIn("original description", project.config.visual_generation.image_style_prompt)
        self.assertNotIn("a completely different description", project.config.visual_generation.image_style_prompt)

    def test_attaching_to_a_nonexistent_series_raises_not_found(self):
        project_id = self._make_project("Episode 1")
        with self.assertRaises(NotFoundError):
            attach_project_to_series(project_id, AttachSeriesRequest(series_id=999))

    def test_attaching_a_nonexistent_project_raises_not_found(self):
        series = create_series("My Series", "male, 28, grey hoodie")
        with self.assertRaises(NotFoundError):
            attach_project_to_series(999, AttachSeriesRequest(series_id=series.id))


class ListSeriesProjectsTests(_SeriesProjectTestCase):
    def test_returns_episodes_in_order(self):
        series = create_series("My Series", "male, 28, grey hoodie")
        third_id = self._make_project("Episode 3")
        first_id = self._make_project("Episode 1")
        second_id = self._make_project("Episode 2")
        attach_project_to_series(first_id, AttachSeriesRequest(series_id=series.id))
        attach_project_to_series(second_id, AttachSeriesRequest(series_id=series.id))
        attach_project_to_series(third_id, AttachSeriesRequest(series_id=series.id))

        result = list_series_projects(series.id)

        self.assertEqual([p.episode_number for p in result], [1, 2, 3])
        self.assertEqual([p.name for p in result], ["Episode 1", "Episode 2", "Episode 3"])

    def test_missing_series_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            list_series_projects(999)

    def test_series_with_no_episodes_returns_empty_list(self):
        series = create_series("Empty Series", "")
        self.assertEqual(list_series_projects(series.id), [])


if __name__ == "__main__":
    unittest.main()
