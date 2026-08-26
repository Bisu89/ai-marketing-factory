"""Tests for Task 59 -- see docs/features/59-ai-image-generation.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness.

Two layers, same split test_content_stage.py already established:
  - ImageGenerationTests/IdempotencyTests/SoftFailureTests exercise the
    real app.api.v1.endpoints.imagegen_generate.generate_project_images
    logic (idempotent reuse, per-beat soft-fail, cost calc), with only
    image_client.generate_beat_image mocked at its own module boundary
    (no real OpenAI call).
  - PipelineWiringTests exercise factory_pipeline's own PREPARING_VISUALS
    mode dispatch/checkpoint/error-translation, with generate_project_images
    itself mocked at the factory_pipeline module boundary -- exactly the
    same pattern test_content_stage.py already uses for
    generate_content_brief/generate_script.
"""

import unittest
from unittest.mock import patch

from app.api.v1.endpoints.factory_pipeline import _stage_generate_images
from app.api.v1.endpoints.imagegen_generate import (
    ImageGenerationResult,
    _image_size_for_profile,
    _orientation_phrase,
    generate_project_images,
)
from app.core.render_profile import SOCIAL_LANDSCAPE, SOCIAL_VERTICAL
from app.modules.ai.image_client import IMAGE_COST_USD, IMAGE_SIZE_LANDSCAPE, IMAGE_SIZE_PORTRAIT, ImageGenError
from app.modules.asset.models import Asset
from app.modules.beat.project_service import create_project, get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ProjectConfig, RenderProjectConfig, VisualGenerationProjectConfig
from app.modules.factory import service as factory_service
from app.modules.factory.schemas import IMAGE_GENERATION_FAILED
from tests.api.test_factory_pipeline import _FactoryTestCase, _fake_beat_plan


def _fake_generate_beat_image_writes_a_file(api_key, prompt, output_path, size=None):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake png bytes")


class _ImageGenTestCase(_FactoryTestCase):
    # app.modules.beat.project_service.SessionLocal is already patched for
    # the whole test by _FactoryTestCase.setUp's own patchers list -- these
    # project_service calls need no additional per-call patch context.
    def _ai_generated_project(self, name: str, num_beats: int = 3) -> int:
        config = ProjectConfig(visual_generation=VisualGenerationProjectConfig(mode="ai_generated"))
        project_id = create_project(name, "A short test script.", config)
        plan = _fake_beat_plan("A short test script.", num_beats).model_copy(update={"config": config})
        update_project_beat_plan(project_id, plan)
        return project_id


class ImageGenerationTests(_ImageGenTestCase):
    def test_generates_and_registers_a_real_asset_for_every_pending_beat(self):
        self.settings.openai_api_key = "fake-openai-key"
        project_id = self._ai_generated_project("Full Gen", num_beats=3)

        with (
            patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image", side_effect=_fake_generate_beat_image_writes_a_file),
            patch("app.api.v1.endpoints.imagegen_generate.SessionLocal", self.TestSessionLocal),
        ):
            result = generate_project_images(project_id, self.settings)

        self.assertTrue(result.generated)
        self.assertEqual(result.image_count, 3)
        self.assertAlmostEqual(result.cost_usd, round(3 * IMAGE_COST_USD, 4))

        draft = get_project_draft(project_id)
        for beat in draft.beats:
            self.assertIsNotNone(beat.asset_id)

    def test_custom_image_style_prompt_is_appended_to_every_beat_prompt(self):
        self.settings.openai_api_key = "fake-openai-key"
        config = ProjectConfig(
            visual_generation=VisualGenerationProjectConfig(
                mode="ai_generated", image_style_prompt="watercolor illustration, pastel colors"
            )
        )
        project_id = create_project("Styled", "A short test script.", config)
        plan = _fake_beat_plan("A short test script.", 2).model_copy(update={"config": config})
        update_project_beat_plan(project_id, plan)

        captured_prompts = []

        def _capture_and_write(api_key, prompt, output_path, size=None):
            captured_prompts.append(prompt)
            _fake_generate_beat_image_writes_a_file(api_key, prompt, output_path, size)

        with (
            patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image", side_effect=_capture_and_write),
            patch("app.api.v1.endpoints.imagegen_generate.SessionLocal", self.TestSessionLocal),
        ):
            generate_project_images(project_id, self.settings)

        self.assertEqual(len(captured_prompts), 2)
        for prompt in captured_prompts:
            self.assertIn("watercolor illustration, pastel colors", prompt)

    def test_no_openai_key_configured_raises_image_gen_error(self):
        project_id = self._ai_generated_project("No Key")
        self.assertIsNone(self.settings.openai_api_key)
        with self.assertRaises(ImageGenError):
            generate_project_images(project_id, self.settings)

    def test_no_pending_beats_is_a_true_noop(self):
        self.settings.openai_api_key = "fake-openai-key"
        project_id = self._ai_generated_project("Already Assigned", num_beats=1)
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[b.model_copy(update={"asset_id": self.asset_id}) for b in draft.beats],
        )
        update_project_beat_plan(project_id, plan)

        with patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image") as mock_gen:
            result = generate_project_images(project_id, self.settings)
            mock_gen.assert_not_called()
        self.assertFalse(result.generated)
        self.assertEqual(result.image_count, 0)
        self.assertEqual(result.cost_usd, 0.0)


class SoftFailureTests(_ImageGenTestCase):
    def test_one_beat_failing_leaves_only_that_beat_unassigned(self):
        self.settings.openai_api_key = "fake-openai-key"
        project_id = self._ai_generated_project("Partial Failure", num_beats=3)

        def _fail_beat_02(api_key, prompt, output_path, size=None):
            if "beat_02" in str(output_path):
                raise ImageGenError("content policy rejection")
            _fake_generate_beat_image_writes_a_file(api_key, prompt, output_path, size)

        with (
            patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image", side_effect=_fail_beat_02),
            patch("app.api.v1.endpoints.imagegen_generate.SessionLocal", self.TestSessionLocal),
        ):
            result = generate_project_images(project_id, self.settings)

        self.assertTrue(result.generated)  # at least one real call happened
        self.assertEqual(result.image_count, 2)  # never fails the whole stage over one beat

        draft = get_project_draft(project_id)
        by_id = {b.id: b for b in draft.beats}
        self.assertIsNotNone(by_id["beat_01"].asset_id)
        self.assertIsNone(by_id["beat_02"].asset_id)
        self.assertIsNotNone(by_id["beat_03"].asset_id)


class IdempotencyTests(_ImageGenTestCase):
    def test_retry_never_regenerates_an_already_assigned_beat(self):
        self.settings.openai_api_key = "fake-openai-key"
        project_id = self._ai_generated_project("Retry Safe", num_beats=2)

        with (
            patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image", side_effect=_fake_generate_beat_image_writes_a_file) as mock_gen,
            patch("app.api.v1.endpoints.imagegen_generate.SessionLocal", self.TestSessionLocal),
        ):
            first = generate_project_images(project_id, self.settings)
            self.assertEqual(mock_gen.call_count, 2)

            second = generate_project_images(project_id, self.settings)
            self.assertEqual(mock_gen.call_count, 2)  # never re-billed/re-called

        self.assertTrue(first.generated)
        self.assertFalse(second.generated)
        self.assertEqual(second.image_count, 0)


class LandscapeProfileTests(_ImageGenTestCase):
    """Real user request (docs/features/108-landscape-render-profile.md):
    a landscape (16:9) render profile alongside this app's original
    portrait one -- AI image generation must actually request landscape
    images (and register the right Asset dimensions) for a project using it.
    """

    def test_image_size_for_profile_derives_from_width_vs_height_not_name(self):
        self.assertEqual(_image_size_for_profile(SOCIAL_VERTICAL), IMAGE_SIZE_PORTRAIT)
        self.assertEqual(_image_size_for_profile(SOCIAL_LANDSCAPE), IMAGE_SIZE_LANDSCAPE)

    def test_orientation_phrase_matches_each_size(self):
        self.assertIn("vertical", _orientation_phrase(IMAGE_SIZE_PORTRAIT))
        self.assertIn("horizontal", _orientation_phrase(IMAGE_SIZE_LANDSCAPE))

    def test_landscape_project_requests_landscape_images_and_registers_landscape_asset(self):
        self.settings.openai_api_key = "fake-openai-key"
        config = ProjectConfig(
            render=RenderProjectConfig(profile="SOCIAL_LANDSCAPE"),
            visual_generation=VisualGenerationProjectConfig(mode="ai_generated"),
        )
        project_id = create_project("Landscape Series", "A short test script.", config)
        plan = _fake_beat_plan("A short test script.", 1).model_copy(update={"config": config})
        update_project_beat_plan(project_id, plan)

        captured_sizes = []
        captured_prompts = []

        def _capture(api_key, prompt, output_path, size=None):
            captured_sizes.append(size)
            captured_prompts.append(prompt)
            _fake_generate_beat_image_writes_a_file(api_key, prompt, output_path, size)

        with (
            patch("app.api.v1.endpoints.imagegen_generate.generate_beat_image", side_effect=_capture),
            patch("app.api.v1.endpoints.imagegen_generate.SessionLocal", self.TestSessionLocal),
        ):
            generate_project_images(project_id, self.settings)

        self.assertEqual(captured_sizes, [IMAGE_SIZE_LANDSCAPE])
        self.assertIn("horizontal 16:9 composition", captured_prompts[0])

        draft = get_project_draft(project_id)
        asset_id = draft.beats[0].asset_id
        self.assertIsNotNone(asset_id)
        db = self.TestSessionLocal()
        try:
            asset = db.get(Asset, asset_id)
            self.assertEqual((asset.width, asset.height), (1536, 1024))
        finally:
            db.close()


class PipelineWiringTests(_FactoryTestCase):
    def test_stage_translates_image_gen_error_to_stable_code(self):
        project_id = self._create_project("Wiring Error")
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_project_images",
            side_effect=ImageGenError("boom"),
        ):
            with self.assertRaises(Exception) as ctx:
                _stage_generate_images(project_id, self.settings)
        self.assertEqual(ctx.exception.code, IMAGE_GENERATION_FAILED)
        self.assertEqual(ctx.exception.stage, "PREPARING_VISUALS")

    def test_library_mode_never_calls_image_generation(self):
        project_id = self._create_project("Library Mode")
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Part one.", duration=1.5, asset_id=self.asset_id)]
        update_project_beat_plan(project_id, BeatPlan(script_text="A short test script.", beats=beats))
        with patch("app.api.v1.endpoints.factory_pipeline.generate_project_images") as mock_gen:
            run = self._run_sync(project_id)
            mock_gen.assert_not_called()
        self.assertEqual(run.status, "QUEUED")  # unaffected -- default "library" mode, unchanged from before Task 59
        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["PREPARING_VISUALS"].status, "SKIPPED")

    def test_ai_generated_mode_runs_the_real_stage_and_persists_count_and_cost(self):
        config = ProjectConfig(visual_generation=VisualGenerationProjectConfig(mode="ai_generated"))
        project_id = create_project("AI Mode Full Run", "A short test script.", config)
        beats = [
            Beat(id="b1", order=1, type=BeatType.BODY, narration="Part one.", duration=1.5),
        ]
        update_project_beat_plan(project_id, BeatPlan(script_text="A short test script.", beats=beats, config=config))

        fake_result = ImageGenerationResult(generated=True, image_count=1, cost_usd=IMAGE_COST_USD)

        def _assign_and_return(project_id, settings):
            draft = get_project_draft(project_id)
            plan = BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[b.model_copy(update={"asset_id": self.asset_id}) for b in draft.beats],
            )
            update_project_beat_plan(project_id, plan)
            return fake_result

        with patch("app.api.v1.endpoints.factory_pipeline.generate_project_images", side_effect=_assign_and_return):
            run = self._run_sync(project_id)

        self.assertEqual(run.status, "QUEUED")
        self.assertEqual(run.visual_generation_image_count, 1)
        self.assertAlmostEqual(run.visual_generation_cost_usd, IMAGE_COST_USD)
        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["PREPARING_VISUALS"].status, "COMPLETED")
        self.assertEqual(checkpoints["PREPARING_VISUALS"].checkpoint_metadata["image_count"], 1)


if __name__ == "__main__":
    unittest.main()
