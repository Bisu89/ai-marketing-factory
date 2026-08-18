"""Tests for Task 27 -- see docs/features/53-thumbnail-metadata-package.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness. Uses
the real LocalTTSProvider, real FFmpeg Motion/Final-Composer rendering,
real Audio Master mixing, real Captions, and real Pillow/FFmpeg thumbnail
extraction throughout (no mocking of any pipeline stage) -- the same
"exercise the real engine" precedent every prior stage's own tests already
established.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.api.v1.endpoints.audio_generate import generate_project_audio_master
from app.api.v1.endpoints.caption_generate import generate_project_captions
from app.api.v1.endpoints.factory_pipeline import FactoryStageError, _stage_package, register_factory_event_handlers
from app.api.v1.endpoints.package_generate import (
    generate_project_package,
    get_project_package,
    metadata_path,
    package_is_valid,
    package_was_attempted,
    regenerate_metadata,
    regenerate_package,
    regenerate_thumbnail,
    set_package_overrides,
    thumbnail_path,
    validate_package,
    PackageError,
    PackageOverridesIn,
)
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ContentBrief, ProjectConfig
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_render import FFMPEG_AVAILABLE
from tests.api.test_factory_pipeline import _FactoryTestCase


def _make_textured_image(path: Path, seed: int, size: tuple[int, int] = (135, 240)) -> Path:
    """A real, non-flat image -- Task 27's own real bug (thumbnail frame
    rejection against flat solid-color test fixtures, found during manual
    verification) means every fixture in this file needs genuine texture,
    not a plain color swatch.
    """
    small = Image.new("RGB", size)
    px = small.load()
    base = (20 * seed % 200, 120, 200 - (20 * seed % 150))
    for x in range(size[0]):
        for y in range(size[1]):
            variance = (x * 7 + y * 3 + seed * 11) % 80
            px[x, y] = (
                max(0, min(255, base[0] + variance - 40)),
                max(0, min(255, base[1] + (variance * 2) % 70 - 35)),
                max(0, min(255, base[2] + (variance * 3) % 60 - 30)),
            )
    img = small.resize((1080, 1920), Image.LANCZOS)
    img.save(path, "JPEG", quality=90)
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class _PackageStageTestCase(_FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.service.start()
        register_factory_event_handlers(self.event_bus)

    def _full_pipeline_project(
        self, name: str, texts: list[str], *, content_brief: ContentBrief | None = None, config: ProjectConfig | None = None,
    ) -> int:
        from app.modules.beat.project_service import create_project

        project_config = config or ProjectConfig()
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project(name, "placeholder script", project_config)

        beats = []
        for i, text in enumerate(texts, start=1):
            image = _make_textured_image(self.tmp_path / f"{name}_beat{i}.jpg", seed=i)
            asset_id = self._register_image_asset(image)
            beat_type = BeatType.HOOK if i == 1 else BeatType.BODY
            beats.append(Beat(id=f"b{i}", order=i, type=beat_type, narration=text, duration=2.0, asset_id=asset_id))

        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config,
            content_brief=content_brief,
        )
        update_project_beat_plan(project_id, plan)

        generate_project_narration(project_id, self.settings)
        generate_project_audio_master(project_id, self.settings)
        generate_project_captions(project_id, self.settings)
        return project_id

    def _render_and_wait(self, project_id: int):
        from app.api.v1.endpoints.factory_pipeline import _stage_render
        from app.modules.factory import service as factory_service
        import time

        run, _created = factory_service.create_run(project_id)
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name,
            config=draft.config, content_brief=draft.content_brief,
        )
        _stage_render(run.id, project_id, plan, self.settings, self.service)

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            current = factory_service.get_run(run.id)
            if current.status in ("COMPLETED", "FAILED", "CANCELLED"):
                return current
            time.sleep(0.2)
        self.fail("FactoryRun never reached a terminal status")

    def _content_brief(self) -> ContentBrief:
        return ContentBrief(
            topic="long distance relationships", audience="young adults", angle="betrayal and healing",
            emotion="bittersweet", hook_strategy="open with a direct question", tone="reflective",
            pacing="slow build", core_message="She finally told him why she left after ten years",
            cta="Follow for more real stories",
        )


class EndToEndPackageTests(_PackageStageTestCase):
    def test_full_pipeline_produces_a_complete_package(self):
        project_id = self._full_pipeline_project(
            "Package E2E", ["This is the amazing hook.", "This is the main story now.", "And that's the ending."],
            content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        pkg = get_project_package(project_id, self.settings)
        self.assertTrue(pkg.is_complete)
        self.assertIsNotNone(pkg.title)
        self.assertIsNotNone(pkg.description)
        self.assertGreater(len(pkg.hashtags), 0)
        self.assertIsNotNone(pkg.thumbnail_path)
        self.assertTrue(Path(pkg.thumbnail_path).exists())
        self.assertIsNotNone(pkg.video_path)
        self.assertTrue(Path(pkg.video_path).exists())

        validate_package(project_id, self.settings)  # must not raise
        self.assertTrue(package_is_valid(project_id, self.settings))
        self.assertTrue(package_was_attempted(project_id, self.settings.library_dir))


class MetadataFieldsTests(_PackageStageTestCase):
    def test_metadata_json_has_all_required_fields_correctly_serialized(self):
        project_id = self._full_pipeline_project(
            "Metadata Fields", ["Some narration text for this beat."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            meta_file = metadata_path(job)
        finally:
            db.close()
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        for key in (
            "title", "description", "hashtags", "language", "category", "duration",
            "aspect_ratio", "width", "height", "thumbnail", "video", "platform_profile",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["thumbnail"], "thumbnail.jpg")
        self.assertGreater(data["duration"], 0)
        self.assertEqual(data["aspect_ratio"], "9:16")


class ManualOverrideTests(_PackageStageTestCase):
    def test_manual_title_is_not_replaced_by_generated_title(self):
        project_id = self._full_pipeline_project(
            "Manual Title Override", ["Some narration text."], content_brief=self._content_brief(),
        )
        set_package_overrides(project_id, PackageOverridesIn(title="My Hand-Picked Title"))
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        pkg = get_project_package(project_id, self.settings)
        self.assertEqual(pkg.title, "My Hand-Picked Title")

    def test_manual_hashtags_are_not_replaced_by_generated_hashtags(self):
        project_id = self._full_pipeline_project(
            "Manual Hashtags Override", ["Some narration text."], content_brief=self._content_brief(),
        )
        set_package_overrides(project_id, PackageOverridesIn(hashtags=["#MyOwnTag", "#Second"]))
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        pkg = get_project_package(project_id, self.settings)
        self.assertEqual(pkg.hashtags, ["#MyOwnTag", "#Second"])

    def test_clearing_a_manual_override_reverts_to_generated(self):
        project_id = self._full_pipeline_project(
            "Clear Override", ["Some narration text."], content_brief=self._content_brief(),
        )
        set_package_overrides(project_id, PackageOverridesIn(title="Temporary Title"))
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        pkg = get_project_package(project_id, self.settings)
        self.assertEqual(pkg.title, "Temporary Title")

        set_package_overrides(project_id, PackageOverridesIn(clear_title=True))
        regenerate_package(project_id, self.settings)
        pkg_after = get_project_package(project_id, self.settings)
        self.assertNotEqual(pkg_after.title, "Temporary Title")


class CacheTests(_PackageStageTestCase):
    def test_second_generate_call_with_unchanged_state_does_not_rewrite(self):
        project_id = self._full_pipeline_project(
            "Cache Reuse", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            thumb_file = thumbnail_path(job)
            meta_file = metadata_path(job)
        finally:
            db.close()
        thumb_mtime = thumb_file.stat().st_mtime_ns
        meta_mtime = meta_file.stat().st_mtime_ns

        second = generate_project_package(project_id, self.settings)
        self.assertFalse(second)
        self.assertEqual(thumb_file.stat().st_mtime_ns, thumb_mtime)
        self.assertEqual(meta_file.stat().st_mtime_ns, meta_mtime)


class InvalidationTests(_PackageStageTestCase):
    def test_description_change_invalidates_metadata_but_not_thumbnail(self):
        project_id = self._full_pipeline_project(
            "Description Invalidation", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            thumb_file = thumbnail_path(job)
            meta_file = metadata_path(job)
        finally:
            db.close()
        thumb_mtime = thumb_file.stat().st_mtime_ns
        meta_content_before = meta_file.read_text(encoding="utf-8")

        set_package_overrides(project_id, PackageOverridesIn(description="A brand new manual description."))
        regenerated = generate_project_package(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertEqual(thumb_file.stat().st_mtime_ns, thumb_mtime)  # thumbnail untouched
        self.assertNotEqual(meta_file.read_text(encoding="utf-8"), meta_content_before)  # metadata changed

    def test_final_video_change_invalidates_thumbnail_and_package(self):
        project_id = self._full_pipeline_project(
            "Video Change Invalidation", ["Some narration text for this one beat."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            thumb_file = thumbnail_path(job)
        finally:
            db.close()
        original_thumb_bytes = thumb_file.read_bytes()

        # Simulate a genuinely different final video landing at the same
        # path (e.g. a real re-render) -- a real ffmpeg re-encode with
        # different visual content, not just appended bytes (which a real
        # MP4 decoder simply ignores as trailing garbage, changing the
        # file's own identity for fingerprinting purposes without changing
        # a single decoded pixel -- confirmed by a real test failure while
        # building this suite). The thumbnail fingerprint keys off file
        # identity (mtime+size), matching every other stage's own artifact
        # fingerprint convention.
        import subprocess
        import time as time_module

        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            real_video_path = Path(job.output_path)
        finally:
            db.close()
        time_module.sleep(0.05)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=size=1080x1920:rate=24",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-t", "3", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(real_video_path)],
            check=True, stdin=subprocess.DEVNULL,
        )

        regenerated = generate_project_package(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(thumb_file.read_bytes(), original_thumb_bytes)


class IncompletePackageTests(_PackageStageTestCase):
    def test_missing_thumbnail_is_detected_as_incomplete(self):
        project_id = self._full_pipeline_project(
            "Incomplete Package", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            thumb_file = thumbnail_path(job)
        finally:
            db.close()
        thumb_file.unlink()

        with self.assertRaises(PackageError) as ctx:
            validate_package(project_id, self.settings)
        self.assertEqual(ctx.exception.code, "PACKAGE_INCOMPLETE")
        self.assertFalse(package_is_valid(project_id, self.settings))

    def test_no_completed_render_yet_is_incomplete(self):
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Never Rendered", "placeholder", ProjectConfig())
        with self.assertRaises(PackageError) as ctx:
            validate_package(project_id, self.settings)
        self.assertEqual(ctx.exception.code, "PACKAGE_INCOMPLETE")


class RegenerateIndependentlyTests(_PackageStageTestCase):
    def test_regenerate_thumbnail_does_not_touch_metadata_cache(self):
        project_id = self._full_pipeline_project(
            "Independent Regenerate", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        draft = get_project_draft(project_id)
        db = self.TestSessionLocal()
        try:
            job = db.get(VideoComposeJob, draft.render_job_id)
            meta_file = metadata_path(job)
        finally:
            db.close()
        meta_mtime = meta_file.stat().st_mtime_ns

        result = regenerate_thumbnail(project_id, self.settings)
        self.assertTrue(result["generated"])
        self.assertEqual(meta_file.stat().st_mtime_ns, meta_mtime)

    def test_regenerate_metadata_endpoint_bypasses_its_own_cache(self):
        project_id = self._full_pipeline_project(
            "Regenerate Metadata Only", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        result = regenerate_metadata(project_id, self.settings)
        self.assertTrue(result["generated"])


class StageErrorTranslationTests(_PackageStageTestCase):
    def test_a_package_error_is_translated_into_a_factory_stage_error(self):
        project_id = self._full_pipeline_project(
            "Stage Error Translation", ["Some narration text."], content_brief=self._content_brief(),
        )
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_project_package",
            side_effect=PackageError("PACKAGE_INCOMPLETE", "forced for translation test"),
        ):
            from app.modules.factory import service as factory_service

            run, _created = factory_service.create_run(project_id)
            with self.assertRaises(FactoryStageError) as ctx:
                _stage_package(run.id, project_id, self.settings)
        self.assertEqual(ctx.exception.code, "PACKAGE_INCOMPLETE")
        self.assertEqual(ctx.exception.stage, "PACKAGING")


class CrashRecoveryTests(_PackageStageTestCase):
    def test_run_stuck_in_packaging_is_marked_interrupted_on_reconcile(self):
        from app.api.v1.endpoints.factory_pipeline import reconcile_factory_runs_on_startup
        from app.modules.factory import service as factory_service

        project_id = self._full_pipeline_project(
            "Packaging Crash", ["Some narration text."], content_brief=self._content_brief(),
        )
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="PACKAGING")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "PACKAGING")

    def test_retry_from_packaging_never_re_renders_the_video(self):
        from app.api.v1.endpoints.factory_pipeline import retry_run
        from app.modules.factory import service as factory_service

        project_id = self._full_pipeline_project(
            "Packaging Retry", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        original_render_job_id = run.render_job_id
        # Force this already-COMPLETED run back to FAILED at PACKAGING, as
        # if the app crashed right there -- render_job_id must survive
        # untouched (the whole point: resume Packaging, never re-render).
        factory_service.set_run_fields(
            run.id, status="FAILED", failed_stage="PACKAGING", error_code="FACTORY_INTERRUPTED",
            error_message="simulated crash", completed_at=None,
        )

        retried = retry_run(run.id, self.settings, self.service)
        self.assertEqual(retried.status, "COMPLETED")
        self.assertEqual(retried.render_job_id, original_render_job_id)


class BatchTests(_PackageStageTestCase):
    def test_three_projects_each_get_a_complete_package(self):
        project_ids = [
            self._full_pipeline_project(f"Batch Package {i}", [f"Batch narration number {i}."], content_brief=self._content_brief())
            for i in range(1, 4)
        ]
        for project_id in project_ids:
            run = self._render_and_wait(project_id)
            self.assertEqual(run.status, "COMPLETED")
            self.assertTrue(package_is_valid(project_id, self.settings))


if __name__ == "__main__":
    unittest.main()
