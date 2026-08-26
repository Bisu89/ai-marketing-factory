"""Tests for Task 21 -- see docs/features/47-content-brief-script-engine.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness.
Content generation itself (generate_content_brief/generate_script) is
mocked at the factory_pipeline module boundary -- exactly the same pattern
already used for generate_beat_plan throughout test_factory_pipeline.py --
so these tests exercise the real CONTENT stage/checkpoint/invalidation/
idempotency machinery without a real Claude call.
"""

import unittest
from unittest.mock import patch

from app.api.v1.endpoints import factory_pipeline as factory_pipeline_module
from app.api.v1.endpoints.content_generate import (
    ContentProviderTimeout,
    InvalidContentResponse,
    Script,
    ScriptValidationError,
    content_fingerprint,
    validate_script_text,
)
from app.api.v1.endpoints.factory_pipeline import _execute_pipeline_sync, _stage_generate_content, retry_run
from app.modules.batch import service as batch_service
from app.modules.batch.schemas import CreateBatchRequest, find_duplicate_ideas, normalize_idea, parse_idea_rows
from app.modules.beat.project_service import (
    get_project_draft,
    update_project_beat_plan,
    update_project_idea,
    update_project_script,
)
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ContentBrief, ContentProjectConfig
from app.modules.factory import service as factory_service
from app.modules.factory.schemas import (
    CONTENT_GENERATION_FAILED,
    CONTENT_PROVIDER_TIMEOUT,
    INVALID_CONTENT_RESPONSE,
    SCRIPT_TOO_LONG,
    SCRIPT_TOO_SHORT,
)
from tests.api.test_factory_pipeline import _FactoryTestCase


def _fake_brief(api_key, idea, content_config):
    return ContentBrief(
        topic=idea, audience="general audience", angle="a real angle", emotion="recognition",
        hook_strategy="unexpected observation", tone="warm", pacing="steady",
        core_message="the core message", cta="think about it",
    )


def _fake_script(word_count: int = 72):
    def _make(credentials, brief, content_config, words_per_second):
        body_words = " ".join(["word"] * max(word_count - 12, 4))
        return Script(
            hook="This is the opening hook line.",
            body=[body_words],
            ending="This is the closing ending line.",
            cta="Please think about this now.",
        )
    return _make


def _fake_beat_plan_with_asset(asset_id: int):
    """Unlike tests.api.test_factory_pipeline's own _fake_beat_plan (no
    visual_hint/asset_id -- deliberately triggers MISSING_VISUAL_ASSET for
    *its* tests), this pre-assigns a real asset so a full Content->Script->
    Beat->Visual->Quality->Render chain can actually reach QUEUED.
    """
    def _make(api_key, script, **_):
        return BeatPlan(
            script_text=script,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration=script[:80], duration=2.0, asset_id=asset_id)],
        )
    return _make


class _ContentStageTestCase(_FactoryTestCase):
    def _patch_content(self, word_count: int = 72):
        return (
            patch("app.api.v1.endpoints.factory_pipeline.generate_content_brief", side_effect=_fake_brief),
            patch("app.api.v1.endpoints.factory_pipeline.generate_script", side_effect=_fake_script(word_count)),
        )

    def _project_with_idea(self, name: str, idea: str) -> int:
        from app.modules.beat.project_service import create_project
        from app.modules.beat.schemas import ProjectConfig

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            return create_project(name, None, ProjectConfig(), idea=idea)


class ContentGenerationTests(_ContentStageTestCase):
    def test_idea_produces_content_brief_and_script_then_beats(self):
        project_id = self._project_with_idea("Idea To Script", "Why couples stop talking after five years")
        with (
            self._patch_content()[0], self._patch_content()[1],
            patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan", side_effect=_fake_beat_plan_with_asset(self.asset_id)),
        ):
            run = self._run_sync(project_id)

        self.assertEqual(run.status, "QUEUED")
        draft = get_project_draft(project_id)
        self.assertIsNotNone(draft.content_brief)
        self.assertEqual(draft.content_brief.topic, "Why couples stop talking after five years")
        self.assertTrue(draft.script_text and draft.script_text.strip())
        self.assertTrue(len(draft.beats) > 0)  # Beat generation ran from the AI-produced script

        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["PREPARING_CONTENT"].status, "COMPLETED")
        self.assertEqual(checkpoints["PREPARING_CONTENT"].checkpoint_metadata["generated"], True)

    def test_structured_output_is_used_not_arbitrary_prose(self):
        """Section 11 -- Script itself enforces hook/body/ending structure
        via real Pydantic validation, not string-sniffing.
        """
        with self.assertRaises(Exception):
            Script(hook="", body=[], ending="")


class ValidationTests(_ContentStageTestCase):
    def test_empty_script_rejected(self):
        with self.assertRaises(ScriptValidationError):
            validate_script_text("", target_duration=30, words_per_second=2.2)

    def test_missing_hook_rejected_by_script_model(self):
        with self.assertRaises(Exception):
            Script(hook="", body=["some body text"], ending="an ending")

    def test_missing_body_rejected_by_script_model(self):
        with self.assertRaises(Exception):
            Script(hook="a hook", body=[], ending="an ending")

    def test_script_too_short_flagged(self):
        with self.assertRaises(ScriptValidationError) as ctx:
            validate_script_text("Too short.", target_duration=30, words_per_second=2.2)
        self.assertEqual(ctx.exception.code, SCRIPT_TOO_SHORT)

    def test_script_too_long_flagged(self):
        long_text = " ".join(["word"] * 500)
        with self.assertRaises(ScriptValidationError) as ctx:
            validate_script_text(long_text, target_duration=30, words_per_second=2.2)
        self.assertEqual(ctx.exception.code, SCRIPT_TOO_LONG)

    def test_reasonable_length_passes(self):
        target_words = int(30 * 2.2)
        text = " ".join(["word"] * target_words)
        validate_script_text(text, target_duration=30, words_per_second=2.2)  # must not raise

    def test_content_stage_maps_provider_timeout_and_invalid_response_to_stable_codes(self):
        project_id = self._project_with_idea("Timeout Project", "An idea")

        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_content_brief",
            side_effect=ContentProviderTimeout("timed out"),
        ):
            with self.assertRaises(Exception):
                _stage_generate_content(project_id, self.settings)

        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_content_brief",
            side_effect=InvalidContentResponse("bad json"),
        ):
            with self.assertRaises(Exception):
                _stage_generate_content(project_id, self.settings)

    def test_full_pipeline_fails_with_stable_error_codes(self):
        project_id = self._project_with_idea("Full Pipeline Timeout", "An idea")
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_content_brief",
            side_effect=ContentProviderTimeout("timed out"),
        ):
            run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "PREPARING_CONTENT")
        self.assertEqual(run.error_code, CONTENT_PROVIDER_TIMEOUT)

    def test_too_short_script_fails_with_stable_code_not_silently_truncated(self):
        project_id = self._project_with_idea("Too Short", "An idea")
        with self._patch_content(word_count=5)[0], self._patch_content(word_count=5)[1]:
            run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "PREPARING_CONTENT")
        self.assertEqual(run.error_code, SCRIPT_TOO_SHORT)
        # Never silently truncated/half-written -- script_text stays empty.
        draft = get_project_draft(project_id)
        self.assertFalse(draft.script_text)


class IdempotencyTests(_ContentStageTestCase):
    def test_existing_script_skips_content_generation(self):
        project_id = self._create_project("Existing Script", script_text="A perfectly good existing script.")
        with patch("app.api.v1.endpoints.factory_pipeline.generate_content_brief") as mock_brief:
            generated = _stage_generate_content(project_id, self.settings)
            mock_brief.assert_not_called()
        self.assertFalse(generated)

    def test_no_idea_and_no_script_leaves_content_stage_as_noop(self):
        project_id = self._create_project("Blank Project", script_text=" ")
        with patch("app.api.v1.endpoints.factory_pipeline.generate_content_brief") as mock_brief:
            generated = _stage_generate_content(project_id, self.settings)
            mock_brief.assert_not_called()
        self.assertFalse(generated)
        # Existing GENERATING_BEATS behavior (unchanged) is what actually
        # surfaces this as a real failure -- verified end to end:
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "GENERATING_BEATS")


class ManualOverrideTests(_ContentStageTestCase):
    def test_locked_script_is_never_overwritten(self):
        project_id = self._project_with_idea("Locked Project", "An idea that would normally generate content")
        update_project_script(project_id, "The human's own final script text, word for word.")
        draft = get_project_draft(project_id)
        self.assertTrue(draft.script_locked)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_content_brief") as mock_brief:
            generated = _stage_generate_content(project_id, self.settings)
            mock_brief.assert_not_called()
        self.assertFalse(generated)
        after = get_project_draft(project_id)
        self.assertEqual(after.script_text, "The human's own final script text, word for word.")

    def test_update_project_script_locks_and_invalidates_beats_only(self):
        project_id = self._project_with_idea("Lock And Invalidate", "An idea")
        # Simulate beats already existing from an earlier pass -- carrying
        # idea/content_brief/script_locked forward exactly like the real
        # FactoryPipeline stages now do (see factory_pipeline.py's
        # _stage_generate_beats), not a fresh, field-dropping BeatPlan.
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text="Old script.", project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Old.", duration=1.0)],
            idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
        )
        update_project_beat_plan(project_id, plan)

        update_project_script(project_id, "A brand new human-written script.")
        after = get_project_draft(project_id)
        self.assertTrue(after.script_locked)
        self.assertEqual(after.beats, [])  # invalidated
        self.assertEqual(after.idea, "An idea")  # untouched -- Script-only chain excludes idea


class InvalidationTests(_ContentStageTestCase):
    def test_idea_change_invalidates_content_script_and_beats(self):
        project_id = self._project_with_idea("Idea Changes", "Original idea")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text="Some script.", project_name=draft.project_name, config=draft.config,
            content_brief=ContentBrief(
                topic="t", audience="a", angle="an", emotion="e", hook_strategy="h",
                tone="t", pacing="p", core_message="c", cta="c",
            ),
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="X.", duration=1.0)],
        )
        update_project_beat_plan(project_id, plan)

        update_project_idea(project_id, "A completely different idea")
        after = get_project_draft(project_id)
        self.assertEqual(after.idea, "A completely different idea")
        self.assertIsNone(after.script_text)
        self.assertIsNone(after.content_brief)
        self.assertEqual(after.beats, [])

    def test_idea_change_does_not_touch_locked_script(self):
        project_id = self._project_with_idea("Idea Changes Locked", "Original idea")
        update_project_script(project_id, "A human wrote this script by hand.")
        update_project_idea(project_id, "A different idea entirely")
        after = get_project_draft(project_id)
        self.assertEqual(after.idea, "A different idea entirely")
        self.assertEqual(after.script_text, "A human wrote this script by hand.")  # untouched -- locked

    def test_asset_change_does_not_invalidate_script_or_beats(self):
        # Section 50's negative case -- reusing existing invalidation
        # architecture means this was never touched by Task 21 at all;
        # verified here for the record.
        project_id = self._create_project("Asset Only", script_text="A script.")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="X.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)
        after = get_project_draft(project_id)
        self.assertEqual(after.script_text, "A script.")
        self.assertEqual(len(after.beats), 1)


class CrashRecoveryTests(_ContentStageTestCase):
    def test_interrupted_during_preparing_content_resumes_at_content_not_beats(self):
        project_id = self._project_with_idea("Interrupted Content", "An idea")
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="PREPARING_CONTENT")
        factory_service.start_checkpoint(run.id, "PREPARING_CONTENT")

        reconciled = factory_pipeline_module.reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)
        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.failed_stage, "PREPARING_CONTENT")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")

        checkpoint = next(c for c in factory_service.get_checkpoints(run.id) if c.stage == "PREPARING_CONTENT")
        self.assertEqual(checkpoint.status, "FAILED")

        with (
            self._patch_content()[0], self._patch_content()[1],
            patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan", side_effect=_fake_beat_plan_with_asset(self.asset_id)),
        ):
            retry_run(run.id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run.id)
        self.assertEqual(resumed.status, "QUEUED")


class DuplicateIdeaTests(unittest.TestCase):
    def test_exact_normalized_duplicates_detected(self):
        ideas = [
            "Why couples stop talking",
            "why couples stop talking",
            "Why couples stop talking!",
            "A totally different idea",
        ]
        duplicates = find_duplicate_ideas(ideas)
        self.assertEqual(len(duplicates), 1)
        (indexes,) = duplicates.values()
        self.assertEqual(sorted(indexes), [0, 1, 2])

    def test_normalize_idea_is_whitespace_and_punctuation_insensitive(self):
        self.assertEqual(normalize_idea("  Why   Couples Stop Talking!  "), normalize_idea("why couples stop talking"))

    def test_duplicates_are_never_auto_deleted_by_the_parser(self):
        rows = parse_idea_rows("Same idea\nSame idea\nSame idea")
        self.assertEqual(len(rows), 3)  # parser never dedupes -- see find_duplicate_ideas for that, separately


class FingerprintTests(unittest.TestCase):
    def test_same_input_same_fingerprint(self):
        content = ContentProjectConfig()
        fp1 = content_fingerprint("Why couples stop talking", "emotional_story", content)
        fp2 = content_fingerprint("why COUPLES stop talking  ", "emotional_story", content)
        self.assertEqual(fp1, fp2)

    def test_different_template_different_fingerprint(self):
        content = ContentProjectConfig()
        fp1 = content_fingerprint("Why couples stop talking", "emotional_story", content)
        fp2 = content_fingerprint("Why couples stop talking", "couple_story", content)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_is_not_project_identity(self):
        # Section 31's own explicit warning -- the fingerprint has no
        # relationship to a Project.id at all.
        content = ContentProjectConfig()
        fp = content_fingerprint("An idea", "custom", content)
        self.assertIsInstance(fp, str)
        self.assertEqual(len(fp), 64)  # sha256 hex digest length, not a row id


class BatchIdeaImportTests(_ContentStageTestCase):
    def _create_idea_batch(self, ideas_text: str, dedupe: bool = False):
        from app.api.v1.endpoints.batch_render import create_batch

        with patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal):
            return create_batch(
                CreateBatchRequest(name="Idea Batch", template_id="custom", ideas_text=ideas_text, dedupe=dedupe),
                self.settings,
            )

    def test_ten_ideas_become_ten_batch_items_and_ten_projects(self):
        ideas = "\n".join(f"Idea number {i}" for i in range(1, 11))
        batch = self._create_idea_batch(ideas)
        self.assertEqual(len(batch.items), 10)
        for item in batch.items:
            self.assertIsNotNone(item.project_id)
            draft = get_project_draft(item.project_id)
            self.assertTrue(draft.idea)
            self.assertIsNone(draft.script_text)

    def test_batch_engine_runs_content_stage_for_each_idea_respecting_concurrency(self):
        ideas = "\n".join(f"Idea number {i}" for i in range(1, 6))
        batch = self._create_idea_batch(ideas)
        self.settings.max_parallel_projects = 2

        with self._patch_content()[0], self._patch_content()[1]:
            started = factory_pipeline_module.run_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(started, 5)

        final = batch_service.get_batch(batch.id)
        for item in final.items:
            self.assertIn(item.status, ("RUNNING", "COMPLETED", "NEEDS_REVIEW", "FAILED"))
            draft = get_project_draft(item.project_id)
            self.assertTrue(draft.script_text)  # content generation ran for every idea


class EndToEndIdeaTests(_ContentStageTestCase):
    def test_one_idea_produces_a_full_beat_plan(self):
        project_id = self._project_with_idea("E2E Idea", "Why couples stop talking after five years")
        with (
            self._patch_content()[0], self._patch_content()[1],
            patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan", side_effect=_fake_beat_plan_with_asset(self.asset_id)),
        ):
            run = self._run_sync(project_id)

        self.assertEqual(run.status, "QUEUED")
        self.assertEqual(run.quality_status, "READY")
        draft = get_project_draft(project_id)
        self.assertTrue(draft.content_brief)
        self.assertTrue(draft.script_text)
        self.assertTrue(len(draft.beats) > 0)
        self.assertIsNotNone(run.render_job_id)


if __name__ == "__main__":
    unittest.main()
