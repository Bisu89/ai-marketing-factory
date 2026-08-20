"""Tests for Task 25 -- see docs/features/51-caption-engine.md. Reuses
tests.api.test_factory_pipeline's own _FactoryTestCase harness. Uses the
real LocalTTSProvider (via voice_generate.generate_project_narration) to
produce real, settled Beat.start/end timing before captioning -- captions
have nothing authoritative to time against otherwise, matching Task 22-24's
own "exercise the real engine" precedent.
"""

import unittest
from unittest.mock import patch

from app.api.v1.endpoints.caption_generate import (
    build_caption_segments,
    caption_fingerprint,
    captions_ass_path,
    captions_is_valid,
    captions_was_attempted,
    generate_project_captions,
    regenerate_captions,
)
from app.api.v1.endpoints.factory_pipeline import FactoryStageError, _stage_generate_captions, reconcile_factory_runs_on_startup
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, CaptionsProjectConfig, ProjectConfig
from app.modules.caption.schemas import CaptionError
from app.modules.voice.schemas import WordTiming
from tests.api.test_factory_pipeline import _FactoryTestCase


class _CaptionStageTestCase(_FactoryTestCase):
    def _project_with_narration(self, name: str, texts: list[str], **config_overrides) -> int:
        from app.modules.beat.project_service import create_project

        config = ProjectConfig(**config_overrides)
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project(name, "placeholder script", config)
        beats = [
            Beat(id=f"b{i}", order=i, type=BeatType.BODY, narration=text, duration=2.0)
            for i, text in enumerate(texts, start=1)
        ]
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        generate_project_narration(project_id, self.settings)  # settles Beat.start/end
        return project_id


class BasicGenerationTests(_CaptionStageTestCase):
    def test_generates_a_valid_ass_file_for_a_settled_project(self):
        project_id = self._project_with_narration("Basic Captions", ["A short piece of narration text for one beat."])
        generated = generate_project_captions(project_id, self.settings)
        self.assertTrue(generated)
        out = captions_ass_path(project_id, self.settings.library_dir)
        self.assertTrue(out.exists())
        content = out.read_text(encoding="utf-8")
        self.assertIn("[Script Info]", content)
        self.assertIn("Dialogue:", content)

    def test_multi_beat_project_produces_segments_for_every_beat(self):
        project_id = self._project_with_narration(
            "Multi Beat Captions",
            ["First beat narration text here.", "Second beat narration text follows now."],
        )
        draft = get_project_draft(project_id)
        segments = build_caption_segments(draft.beats, draft.config.captions)
        beat_ids = {s.beat_id for s in segments}
        self.assertEqual(beat_ids, {"b1", "b2"})

    def test_disabled_captions_produce_no_file(self):
        project_id = self._project_with_narration(
            "Captions Disabled", ["Some narration text."], captions=CaptionsProjectConfig(enabled=False),
        )
        generated = generate_project_captions(project_id, self.settings)
        self.assertFalse(generated)
        self.assertFalse(captions_ass_path(project_id, self.settings.library_dir).exists())

    def test_no_beats_produces_no_file(self):
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("No Beats", "placeholder", ProjectConfig())
        generated = generate_project_captions(project_id, self.settings)
        self.assertFalse(generated)

    def test_beat_without_settled_timing_is_not_captioned(self):
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Unsettled Timing", "placeholder", ProjectConfig())
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some narration text.", duration=2.0)]
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        # Voice was never run -- Beat.start/end are still None.
        generated = generate_project_captions(project_id, self.settings)
        self.assertFalse(generated)


class RealWordTimingIntegrationTests(_CaptionStageTestCase):
    """Task 62 -- see docs/features/62-caption-real-word-timing.md.
    load_word_timestamps is mocked at the caption_generate module boundary
    (the real LocalTTSProvider this harness otherwise uses has no
    word-boundary data at all) -- exercises the real, end-to-end wiring:
    generate_project_captions -> build_caption_segments -> per-beat
    slicing -> split_beat_into_segments's own real-timing path.
    """

    def test_captions_use_real_word_timing_when_available(self):
        # max_words=2 forces "Vợ bước vào phòng." into two 2-word chunks --
        # a single chunk would just inherit the whole Beat window
        # regardless of internal word gaps, telling us nothing.
        project_id = self._project_with_narration(
            "Real Timing", ["Vợ bước vào phòng."], captions=CaptionsProjectConfig(max_words=2),
        )
        draft = get_project_draft(project_id)
        beat = draft.beats[0]
        # A deliberately large, real gap between "bước" and "vào" -- the
        # weighted estimate has no way to know about this natural pause;
        # only real per-word timing positions "vào phòng." correctly.
        half = beat.start + (beat.end - beat.start) * 0.2
        words = [
            WordTiming(text="Vợ", start=beat.start, end=beat.start + 0.2),
            WordTiming(text="bước", start=beat.start + 0.2, end=half),
            WordTiming(text="vào", start=beat.end - 0.4, end=beat.end - 0.2),
            WordTiming(text="phòng.", start=beat.end - 0.2, end=beat.end),
        ]

        with patch("app.api.v1.endpoints.caption_generate.load_word_timestamps", return_value=words):
            generated = generate_project_captions(project_id, self.settings)
        self.assertTrue(generated)

        content = captions_ass_path(project_id, self.settings.library_dir).read_text(encoding="utf-8")
        dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        self.assertGreaterEqual(len(dialogue_lines), 1)
        # The real word "vào" starts at beat.end - 0.4 -- a segment
        # containing it must start there too (within ASS's own centisecond
        # rounding), not at some proportional midpoint estimate.
        last_line = dialogue_lines[-1]
        start_str = last_line.split(",")[1]
        h, m, s = start_str.split(":")
        last_start_seconds = int(h) * 3600 + int(m) * 60 + float(s)
        self.assertAlmostEqual(last_start_seconds, beat.end - 0.4, delta=0.02)

    def test_falls_back_cleanly_when_no_real_timing_available(self):
        # The default LocalTTSProvider path (no mock) -- load_word_timestamps
        # genuinely returns None, and captions still generate correctly via
        # the pre-existing weighted-estimate path.
        project_id = self._project_with_narration("No Real Timing", ["A short piece of narration text for one beat."])
        generated = generate_project_captions(project_id, self.settings)
        self.assertTrue(generated)
        self.assertTrue(captions_is_valid(project_id, self.settings))


class PresetTests(_CaptionStageTestCase):
    def test_each_preset_produces_a_valid_ass_file(self):
        for preset in ("emotional", "cinematic", "word_highlight", "big_statement", "quote", "top"):
            project_id = self._project_with_narration(
                f"Preset {preset}", ["Some narration text for this preset."],
                captions=CaptionsProjectConfig(preset=preset),
            )
            generated = generate_project_captions(project_id, self.settings)
            self.assertTrue(generated)
            self.assertTrue(captions_is_valid(project_id, self.settings))


class IdempotencyTests(_CaptionStageTestCase):
    def test_second_call_with_unchanged_state_does_not_rewrite(self):
        project_id = self._project_with_narration("Caption Reuse", ["Some narration text."])
        first = generate_project_captions(project_id, self.settings)
        self.assertTrue(first)
        out = captions_ass_path(project_id, self.settings.library_dir)
        first_mtime = out.stat().st_mtime_ns

        second = generate_project_captions(project_id, self.settings)
        self.assertFalse(second)
        self.assertEqual(out.stat().st_mtime_ns, first_mtime)

    def test_fingerprint_differs_for_different_preset(self):
        f1 = caption_fingerprint("narration-x", CaptionsProjectConfig(preset="emotional"))
        f2 = caption_fingerprint("narration-x", CaptionsProjectConfig(preset="cinematic"))
        self.assertNotEqual(f1, f2)


class InvalidationTests(_CaptionStageTestCase):
    def test_script_change_invalidates_cached_captions(self):
        project_id = self._project_with_narration("Script Change", ["Original narration text goes here."])
        generate_project_captions(project_id, self.settings)
        out = captions_ass_path(project_id, self.settings.library_dir)
        original_mtime = out.stat().st_mtime_ns

        draft = get_project_draft(project_id)
        edited_beats = [b.model_copy(update={"narration": "Completely different narration content now for this beat."}) for b in draft.beats]
        plan = BeatPlan(script_text=draft.script_text, beats=edited_beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        generate_project_narration(project_id, self.settings)  # Voice resettles timing, same as the real pipeline

        regenerated = generate_project_captions(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(out.stat().st_mtime_ns, original_mtime)

    def test_style_change_invalidates_cached_captions_while_other_stages_stay_untouched(self):
        project_id = self._project_with_narration("Style Change", ["Some narration text."])
        first = generate_project_captions(project_id, self.settings)
        self.assertTrue(first)
        out = captions_ass_path(project_id, self.settings.library_dir)
        original_content = out.read_text(encoding="utf-8")

        draft = get_project_draft(project_id)
        visual_asset_id_before = draft.beats[0].asset_id
        new_config = draft.config.model_copy(
            update={"captions": draft.config.captions.model_copy(update={"preset": "cinematic"})}
        )
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=new_config)
        update_project_beat_plan(project_id, plan)

        regenerated = generate_project_captions(project_id, self.settings)
        self.assertTrue(regenerated)
        self.assertNotEqual(out.read_text(encoding="utf-8"), original_content)

        draft_after = get_project_draft(project_id)
        self.assertEqual(draft_after.beats[0].asset_id, visual_asset_id_before)  # untouched by this stage

    def test_regenerate_endpoint_bypasses_the_cache(self):
        project_id = self._project_with_narration("Explicit Regenerate", ["Some narration text."])
        first = generate_project_captions(project_id, self.settings)
        self.assertTrue(first)
        # A second plain call would hit the cache (proven by IdempotencyTests
        # above) -- regenerate_captions must bypass it regardless.
        second = generate_project_captions(project_id, self.settings)
        self.assertFalse(second)

        result = regenerate_captions(project_id, self.settings)
        self.assertTrue(result["generated"])


class CrashRecoveryTests(_CaptionStageTestCase):
    def test_run_stuck_in_generating_captions_is_marked_interrupted_on_reconcile(self):
        from app.modules.factory import service as factory_service

        project_id = self._project_with_narration("Caption Crash", ["Some narration text."])
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="GENERATING_CAPTIONS")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "GENERATING_CAPTIONS")

    def test_captions_is_valid_false_when_the_file_is_deleted(self):
        project_id = self._project_with_narration("Deleted Captions", ["Some narration text."])
        generate_project_captions(project_id, self.settings)
        out = captions_ass_path(project_id, self.settings.library_dir)
        out.unlink()

        self.assertFalse(captions_is_valid(project_id, self.settings))
        self.assertTrue(captions_was_attempted(project_id, self.settings.library_dir))

    def test_captions_was_never_attempted_for_a_fresh_project(self):
        project_id = self._project_with_narration("Never Ran Captions", ["Some narration text."])
        self.assertFalse(captions_was_attempted(project_id, self.settings.library_dir))


class StageErrorTranslationTests(_CaptionStageTestCase):
    def test_a_caption_error_is_translated_into_a_factory_stage_error(self):
        # Beat's own Pydantic validation (end > start) and
        # CaptionsProjectConfig's own preset field_validator already make
        # every CaptionError this module can raise unreachable through
        # normal, valid application state -- so the translation adapter
        # itself is exercised directly here, the same way a defensive
        # exception-translation branch with no naturally-reachable trigger
        # is tested elsewhere in this codebase.
        project_id = self._project_with_narration("Stage Error Translation", ["Some narration text."])
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_project_captions",
            side_effect=CaptionError("CAPTION_TIMING_INVALID", "forced for translation test"),
        ):
            with self.assertRaises(FactoryStageError) as ctx:
                _stage_generate_captions(project_id, self.settings)
        self.assertEqual(ctx.exception.code, "CAPTION_TIMING_INVALID")
        self.assertEqual(ctx.exception.stage, "GENERATING_CAPTIONS")


class PipelineIntegrationTests(_CaptionStageTestCase):
    def test_full_run_produces_captions_after_voice_motion_and_audio(self):
        from tests.api.test_batch_render import _make_solid_image
        from app.modules.beat.project_service import create_project
        from app.api.v1.endpoints.voice_generate import narration_wav_path
        from app.api.v1.endpoints.audio_generate import audio_master_path

        image = _make_solid_image(self.tmp_path / "caption_pipeline.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(image)

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Captions In Pipeline", "placeholder script", ProjectConfig())
        draft = get_project_draft(project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some real narration text.", duration=2.0, asset_id=asset_id)]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertIn(run.status, ("QUEUED", "NEEDS_REVIEW", "COMPLETED"))

        self.assertTrue(narration_wav_path(project_id, self.settings).exists())
        self.assertTrue(audio_master_path(project_id, self.settings.library_dir).exists())
        self.assertTrue(captions_ass_path(project_id, self.settings.library_dir).exists())


class BatchTests(_CaptionStageTestCase):
    def test_five_projects_complete_the_caption_stage(self):
        from app.api.v1.endpoints.factory_pipeline import run_batch_factory
        from app.modules.batch.schemas import CreateBatchRequest
        from tests.api.test_batch_render import _make_solid_image
        from app.api.v1.endpoints.batch_render import create_batch

        image = _make_solid_image(self.tmp_path / "caption_batch_shared.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(image)

        scripts = "\n---\n".join(f"Batch caption script number {i}." for i in range(1, 6))
        with patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal):
            batch = create_batch(CreateBatchRequest(name="Caption Batch", template_id="custom", scripts_text=scripts), self.settings)

        for item in batch.items:
            draft = get_project_draft(item.project_id)
            beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some narration text for this beat.", duration=2.0, asset_id=asset_id)]
            plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
            update_project_beat_plan(item.project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            started = run_batch_factory(batch.id, self.settings, self.service)
            mock_generate.assert_not_called()

        self.assertEqual(started, 5)

        for item in batch.items:
            self.assertTrue(captions_ass_path(item.project_id, self.settings.library_dir).exists())


if __name__ == "__main__":
    unittest.main()
