"""Quality Gate x Batch integration (Task 16 -- see
docs/features/42-content-quality-gate.md): render_batch() now runs
run_quality_check() on every BEATS_READY item before enqueuing a real
render -- BLOCKED items are SKIPPED, NEEDS_REVIEW items get the new
NEEDS_REVIEW status (batch's own default policy: skip until reviewed,
never silently rendered), and only READY items actually reach
render_composition(). Also covers the read-only
POST /batches/{id}/quality-check summary. Reuses
tests.api.test_batch_render's own _BatchTestCase harness (file-based
SQLite, all SessionLocal patches, real VideoComposerService) rather than
duplicating that setup.
"""

import unittest

from app.api.v1.endpoints.batch_render import check_batch_quality, render_batch
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.batch.service import set_item_fields
from app.modules.beat.project_service import update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from tests.api.test_batch_render import FFMPEG_AVAILABLE, _BatchTestCase


class _QualityBatchTestCase(_BatchTestCase):
    def _register_low_res_image_asset(self, path) -> int:
        db = self._db()
        try:
            asset = AssetService(db).register(
                AssetRegisterIn(filename=path.name, path=str(path), type="image", source="test", width=200, height=200)
            )
            return asset.id
        finally:
            db.close()

    def _set_plan_and_mark_ready(self, item, beats: list[Beat]) -> None:
        project = self._get_project(item.project_id)
        plan = BeatPlan(
            script_text=project.beat_plan_json["script_text"],
            beats=beats,
            project_name=project.beat_plan_json.get("project_name"),
        )
        plan.config.render.profile = "PREVIEW"
        update_project_beat_plan(item.project_id, plan)
        set_item_fields(item.id, status="BEATS_READY", error_message=None)

    def _make_ready_item(self, item, asset_id: int) -> None:
        # No visual_hint at all -> confidence defaults to HIGH (nothing to
        # contradict the assignment); real narration; single well-paced beat.
        self._set_plan_and_mark_ready(
            item,
            [Beat(id="beat_01", order=1, type=BeatType.BODY, narration="A real, complete sentence of narration.", duration=2.0, asset_id=asset_id)],
        )

    def _make_needs_review_item(self, item, low_res_asset_id: int) -> None:
        # No single warning-severity issue is enough to drag the overall
        # score under the READY threshold on its own (by design -- section
        # 5's own "do not over-block"); this combines several real, non-
        # blocking warnings across two dimensions (repeated narrative
        # purpose + a pacing outlier + low-resolution/low-confidence visual
        # matches on every beat) to reliably land in NEEDS_REVIEW without
        # any error-severity issue at all.
        beats = [
            Beat(
                id="beat_01", order=1, type=BeatType.BODY, narration="Narration text one.", duration=2.0,
                asset_id=low_res_asset_id, visual_hint="a completely unrelated concept with different wording",
            ),
            Beat(
                id="beat_02", order=2, type=BeatType.BODY, narration="Narration text two.", duration=2.0,
                asset_id=low_res_asset_id, visual_hint="a completely unrelated concept with different wording",
            ),
            Beat(
                id="beat_03", order=3, type=BeatType.BODY, narration="Narration text three.", duration=20.0,
                asset_id=low_res_asset_id, visual_hint="a completely unrelated concept with different wording",
            ),
        ]
        self._set_plan_and_mark_ready(item, beats)

    def _make_blocked_item(self, item, asset_id: int) -> None:
        # A real, valid, existing asset -- passes the *existing* structural
        # eligibility check fine -- but no narration text at all, while
        # this project's (default "custom" template) audio config has
        # narration_enabled=True. Only the Quality Gate catches this; it
        # proves the gate adds real, additive value beyond the pre-existing
        # eligibility check, not just a duplicate of it.
        self._set_plan_and_mark_ready(
            item,
            [Beat(id="beat_01", order=1, type=BeatType.BODY, narration=None, duration=2.0, asset_id=asset_id)],
        )


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderBatchQualityGateTests(_QualityBatchTestCase):
    def setUp(self):
        super().setUp()
        from tests.api.test_batch_render import _make_solid_image

        self.image = _make_solid_image(self.tmp_path / "shared.jpg", (200, 40, 40))
        self.asset_id = self._register_image_asset(self.image)
        self.low_res_image = _make_solid_image(self.tmp_path / "low_res.jpg", (40, 40, 200), size=(200, 200))
        self.low_res_asset_id = self._register_low_res_image_asset(self.low_res_image)

    def test_ready_item_is_enqueued_for_render(self):
        out = self._create_batch("Quality Ready", "custom", "Only script.")
        self._make_ready_item(out.items[0], self.asset_id)

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertEqual(result.items[0].status, "RENDERING")
        self.assertIsNotNone(result.items[0].render_job_id)

    def test_needs_review_item_is_not_enqueued_by_default(self):
        out = self._create_batch("Quality Review", "custom", "Only script.")
        self._make_needs_review_item(out.items[0], self.low_res_asset_id)

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertEqual(result.items[0].status, "NEEDS_REVIEW")
        self.assertIsNone(result.items[0].render_job_id)
        self.assertIn("Quality Gate", result.items[0].error_message)

    def test_blocked_item_is_skipped_not_enqueued(self):
        out = self._create_batch("Quality Blocked", "custom", "Only script.")
        self._make_blocked_item(out.items[0], self.asset_id)

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertEqual(result.items[0].status, "SKIPPED")
        self.assertIsNone(result.items[0].render_job_id)
        self.assertIn("Quality Gate", result.items[0].error_message)

    def test_ten_projects_six_ready_three_needs_review_one_blocked_yields_six_render_jobs(self):
        # Task 16 section 44's own literal acceptance scenario.
        scripts = "\n---\n".join(f"Script number {i}." for i in range(1, 11))
        out = self._create_batch("Quality Ten Pack", "custom", scripts)
        self.assertEqual(len(out.items), 10)

        for item in out.items[0:6]:
            self._make_ready_item(item, self.asset_id)
        for item in out.items[6:9]:
            self._make_needs_review_item(item, self.low_res_asset_id)
        self._make_blocked_item(out.items[9], self.asset_id)

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        statuses = [item.status for item in result.items]
        self.assertEqual(statuses.count("RENDERING"), 6)
        self.assertEqual(statuses.count("NEEDS_REVIEW"), 3)
        self.assertEqual(statuses.count("SKIPPED"), 1)

        render_job_ids = [item.render_job_id for item in result.items if item.render_job_id is not None]
        self.assertEqual(len(render_job_ids), 6)
        self.assertEqual(len(set(render_job_ids)), 6)  # each is its own real RenderJob, none shared/duplicated


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class BatchQualityCheckEndpointTests(_QualityBatchTestCase):
    def setUp(self):
        super().setUp()
        from tests.api.test_batch_render import _make_solid_image

        self.image = _make_solid_image(self.tmp_path / "shared.jpg", (10, 200, 10))
        self.asset_id = self._register_image_asset(self.image)
        self.low_res_image = _make_solid_image(self.tmp_path / "low_res.jpg", (40, 40, 200), size=(200, 200))
        self.low_res_asset_id = self._register_low_res_image_asset(self.low_res_image)

    def test_quality_check_is_read_only_and_does_not_enqueue_or_mutate(self):
        out = self._create_batch("Dry Run", "custom", "One.\n---\nTwo.\n---\nThree.")
        self._make_ready_item(out.items[0], self.asset_id)
        self._make_needs_review_item(out.items[1], self.low_res_asset_id)
        self._make_blocked_item(out.items[2], self.asset_id)

        db = self._db()
        try:
            summary = check_batch_quality(out.id, db)
        finally:
            db.close()

        self.assertEqual(summary.ready, 1)
        self.assertEqual(summary.needs_review, 1)
        self.assertEqual(summary.blocked, 1)

        # Nothing was actually enqueued or changed -- all three items are
        # still exactly where they started (BEATS_READY), no render_job_id.
        detail_batch = self._get_batch_detail(out.id)
        self.assertTrue(all(item.status == "BEATS_READY" for item in detail_batch.items))
        self.assertTrue(all(item.render_job_id is None for item in detail_batch.items))


if __name__ == "__main__":
    unittest.main()
