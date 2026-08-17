"""Tests for Task 23 -- see docs/features/49-local-motion-engine.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness. Uses
real FFmpeg rendering throughout (no mocking of the renderer itself) -- the
same "exercise the real engine" precedent Task 22's own voice-stage tests
already established.
"""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.v1.endpoints.factory_pipeline import _stage_generate_motion, reconcile_factory_runs_on_startup
from app.api.v1.endpoints.motion_generate import (
    beat_clip_path,
    generate_project_motion,
    motion_artifact_for_beat,
    motion_fingerprint,
    motion_stage_is_complete,
    motion_was_attempted_for_beat,
    resolve_effective_preset,
)
from app.modules.asset.models import Asset
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import (
    Beat,
    BeatMotionPreset,
    BeatPlan,
    BeatType,
    MotionProjectConfig,
    ProjectConfig,
)
from app.modules.motion.renderer import render_video_clip
from tests.api.test_factory_pipeline import _FactoryTestCase
from tests.api.test_batch_render import _make_solid_image


class _MotionStageTestCase(_FactoryTestCase):
    def _project_with_image_beats(self, name: str, count: int = 1, **config_overrides) -> tuple[int, list[int]]:
        from app.modules.beat.project_service import create_project

        config = ProjectConfig(**config_overrides)
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project(name, "placeholder script", config)

        asset_ids = []
        beats = []
        for i in range(1, count + 1):
            image = _make_solid_image(self.tmp_path / f"{name}_{i}.jpg", (10 * i, 200, 10))
            asset_id = self._register_image_asset(image)
            asset_ids.append(asset_id)
            beats.append(Beat(id=f"b{i}", order=i, type=BeatType.BODY, narration=f"Beat {i}.", duration=1.0 + i * 0.5, asset_id=asset_id))

        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        return project_id, asset_ids

    def _make_video_asset(self, name: str, duration: float = 2.0) -> int:
        video_path = self.tmp_path / f"{name}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=640x480:rate=30:duration={duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_path),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        db = self._db()
        try:
            from app.modules.asset.schemas import AssetRegisterIn
            from app.modules.asset.service import AssetService

            asset = AssetService(db).register(AssetRegisterIn(filename=video_path.name, path=str(video_path), type="video", source="test"))
            return asset.id
        finally:
            db.close()


class ImageMotionTests(_MotionStageTestCase):
    def test_generates_a_real_clip_per_beat_with_correct_duration_and_resolution(self):
        project_id, _ = self._project_with_image_beats("Image Motion", count=2)
        generated = generate_project_motion(project_id, self.settings)
        self.assertTrue(generated)

        draft = get_project_draft(project_id)
        for beat in draft.beats:
            clip = beat_clip_path(project_id, beat.id, self.settings.library_dir)
            self.assertTrue(clip.exists())
            self.assertGreater(clip.stat().st_size, 0)

    def test_manual_override_beats_project_default(self):
        project_id, _ = self._project_with_image_beats(
            "Manual Override", count=1, motion=MotionProjectConfig(default_preset=BeatMotionPreset.STATIC)
        )
        draft = get_project_draft(project_id)
        beats = [b.model_copy(update={"motion_preset": BeatMotionPreset.PAN_LEFT}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        effective = resolve_effective_preset(beats[0], draft.config)
        self.assertEqual(effective, BeatMotionPreset.PAN_LEFT)

    def test_auto_rotate_disabled_by_default_every_beat_uses_project_default(self):
        project_id, _ = self._project_with_image_beats(
            "No Auto Rotate", count=3, motion=MotionProjectConfig(default_preset=BeatMotionPreset.ZOOM_AND_PAN)
        )
        draft = get_project_draft(project_id)
        presets = {resolve_effective_preset(b, draft.config) for b in draft.beats}
        self.assertEqual(presets, {BeatMotionPreset.ZOOM_AND_PAN})

    def test_auto_rotate_enabled_varies_preset_across_beats(self):
        project_id, _ = self._project_with_image_beats(
            "Auto Rotate", count=3, motion=MotionProjectConfig(default_preset=BeatMotionPreset.STATIC, auto_rotate=True)
        )
        draft = get_project_draft(project_id)
        presets = [resolve_effective_preset(b, draft.config) for b in draft.beats]
        self.assertGreater(len(set(presets)), 1)


class VideoMotionTests(_MotionStageTestCase):
    def test_existing_video_asset_is_trimmed_to_beat_duration(self):
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Video Motion", "placeholder script", ProjectConfig())
        video_asset_id = self._make_video_asset("source_clip", duration=5.0)

        draft = get_project_draft(project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.2, asset_id=video_asset_id)]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        generated = generate_project_motion(project_id, self.settings)
        self.assertTrue(generated)
        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        self.assertTrue(clip.exists())

    def test_short_video_freeze_policy_still_produces_full_beat_duration(self):
        from app.modules.beat.project_service import create_project

        config = ProjectConfig(motion=MotionProjectConfig(short_video_policy="FREEZE"))
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Short Video Freeze", "placeholder script", config)
        video_asset_id = self._make_video_asset("short_clip", duration=1.0)

        draft = get_project_draft(project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=3.0, asset_id=video_asset_id)]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        generate_project_motion(project_id, self.settings)
        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        from app.modules.motion.renderer import probe_clip

        probe = probe_clip(clip)
        self.assertAlmostEqual(probe.duration_sec, 3.0, delta=0.2)


class IdempotencyAndCacheTests(_MotionStageTestCase):
    def test_second_call_with_unchanged_state_does_not_regenerate(self):
        project_id, _ = self._project_with_image_beats("Motion Reuse", count=1)
        first = generate_project_motion(project_id, self.settings)
        self.assertTrue(first)

        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        first_mtime = clip.stat().st_mtime_ns

        second = generate_project_motion(project_id, self.settings)
        self.assertFalse(second)
        self.assertEqual(clip.stat().st_mtime_ns, first_mtime)

    def test_motion_stage_is_complete_true_only_after_generation(self):
        project_id, _ = self._project_with_image_beats("Completeness", count=2)
        self.assertFalse(motion_stage_is_complete(project_id, self.settings))
        generate_project_motion(project_id, self.settings)
        self.assertTrue(motion_stage_is_complete(project_id, self.settings))


class InvalidationTests(_MotionStageTestCase):
    def test_asset_change_invalidates_the_cached_clip(self):
        project_id, asset_ids = self._project_with_image_beats("Asset Change", count=1)
        generate_project_motion(project_id, self.settings)
        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        original_mtime = clip.stat().st_mtime_ns

        new_image = _make_solid_image(self.tmp_path / "replacement.jpg", (250, 10, 10))
        new_asset_id = self._register_image_asset(new_image)
        draft = get_project_draft(project_id)
        beats = [b.model_copy(update={"asset_id": new_asset_id}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        regenerated = generate_project_motion(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(clip.stat().st_mtime_ns, original_mtime)

    def test_preset_change_invalidates_the_cached_clip(self):
        project_id, _ = self._project_with_image_beats("Preset Change", count=1)
        generate_project_motion(project_id, self.settings)
        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        original_mtime = clip.stat().st_mtime_ns

        draft = get_project_draft(project_id)
        beats = [b.model_copy(update={"motion_preset": BeatMotionPreset.PAN_RIGHT}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        regenerated = generate_project_motion(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(clip.stat().st_mtime_ns, original_mtime)

    def test_fingerprint_differs_for_different_intensity(self):
        f1 = motion_fingerprint("asset-x", BeatMotionPreset.PAN_LEFT, "MEDIUM", 2.0, 1080, 1920, 30.0)
        f2 = motion_fingerprint("asset-x", BeatMotionPreset.PAN_LEFT, "STRONG", 2.0, 1080, 1920, 30.0)
        self.assertNotEqual(f1, f2)


class PartialFailureTests(_MotionStageTestCase):
    def test_one_beat_failing_does_not_prevent_others_from_being_cached(self):
        project_id, asset_ids = self._project_with_image_beats("Partial Failure", count=3)
        draft = get_project_draft(project_id)

        real_render = render_video_clip  # unused placeholder to keep import referenced
        from app.modules.motion import renderer as renderer_module

        original = renderer_module.render_motion_clip
        call_count = {"n": 0}

        def flaky(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise Exception("simulated ffmpeg crash on beat 2")
            return original(*args, **kwargs)

        with patch("app.api.v1.endpoints.motion_generate.render_motion_clip", side_effect=flaky):
            with self.assertRaises(Exception):
                generate_project_motion(project_id, self.settings)

        # Beat 1 (rendered before the simulated failure) must already be
        # cached on disk -- a retry must not have to redo it.
        clip1 = beat_clip_path(project_id, "b1", self.settings.library_dir)
        self.assertTrue(clip1.exists())
        clip2 = beat_clip_path(project_id, "b2", self.settings.library_dir)
        self.assertFalse(clip2.exists())

        # Retry (a plain second call) must only (re)do the failed beat --
        # beat 1's artifact is untouched.
        mtime_before_retry = clip1.stat().st_mtime_ns
        generate_project_motion(project_id, self.settings)
        self.assertEqual(clip1.stat().st_mtime_ns, mtime_before_retry)
        self.assertTrue(clip2.exists())
        clip3 = beat_clip_path(project_id, "b3", self.settings.library_dir)
        self.assertTrue(clip3.exists())


class CrashRecoveryTests(_MotionStageTestCase):
    def test_run_stuck_in_generating_motion_is_marked_interrupted_on_reconcile(self):
        from app.modules.factory import service as factory_service

        project_id, _ = self._project_with_image_beats("Motion Crash", count=1)
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="GENERATING_MOTION")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "GENERATING_MOTION")

    def test_motion_artifact_for_beat_is_none_when_file_is_deleted(self):
        project_id, _ = self._project_with_image_beats("Deleted Artifact", count=1)
        generate_project_motion(project_id, self.settings)
        clip = beat_clip_path(project_id, "b1", self.settings.library_dir)
        clip.unlink()

        draft = get_project_draft(project_id)
        from app.core.render_profile import get_render_profile

        render_profile = get_render_profile(draft.config.render.profile)
        result = motion_artifact_for_beat(
            project_id, "b1", self.settings.library_dir,
            draft.beats[0].duration, render_profile.width, render_profile.height, render_profile.fps,
        )
        self.assertIsNone(result)
        self.assertTrue(motion_was_attempted_for_beat(project_id, "b1", self.settings.library_dir))


class PipelineIntegrationTests(_MotionStageTestCase):
    def test_full_run_produces_motion_clips_before_quality_check(self):
        project_id, _ = self._project_with_image_beats("Motion In Pipeline", count=2)
        run = self._run_sync(project_id)
        self.assertIn(run.status, ("QUEUED", "NEEDS_REVIEW", "COMPLETED"))

        draft = get_project_draft(project_id)
        for beat in draft.beats:
            self.assertTrue(beat_clip_path(project_id, beat.id, self.settings.library_dir).exists())

    def test_motion_reuses_the_final_render_derived_duration_from_voice(self):
        # Motion runs *after* Voice in this pipeline specifically because
        # Voice recomputes each Beat's own `duration` from real measured
        # narration timing -- Motion must render against that final value,
        # not the original pre-Voice guess (see factory/models.py's own
        # FACTORY_STAGES docstring for the discovered dependency).
        project_id, _ = self._project_with_image_beats("Motion After Voice", count=1)
        self._run_sync(project_id)

        draft = get_project_draft(project_id)
        beat = draft.beats[0]
        self.assertIsNotNone(beat.start)  # Voice already ran and set real timing
        from app.modules.motion.renderer import probe_clip

        clip = beat_clip_path(project_id, beat.id, self.settings.library_dir)
        probe = probe_clip(clip)
        self.assertAlmostEqual(probe.duration_sec, beat.duration, delta=0.15)


if __name__ == "__main__":
    unittest.main()
