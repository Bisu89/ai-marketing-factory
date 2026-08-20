"""Tests for app/api/v1/endpoints/quality_gate.py (Task 16 -- see
docs/features/42-content-quality-gate.md) -- the composition root that
bridges real Beat/Asset data into app.modules.quality's pure analyzer.
Route handlers are called directly as plain functions, matching this
codebase's established convention.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints.quality_gate import (
    QualityCheckRequest,
    compute_asset_confidence,
    _resolve_beat_asset_info,
    check_plan_quality,
    check_project_quality,
    run_quality_check,
)
from app.core.config import Settings
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.models import Project
from app.modules.beat.schemas import Beat, BeatPlan, BeatType


def _asset_service_with(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Asset.__table__])
    db = Session(bind=engine)
    return AssetService(db), db, engine


def _register(service: AssetService, tmp_path: Path, name: str, tags=None, **overrides) -> Asset:
    path = tmp_path / name
    path.write_bytes(b"fake bytes")
    return service.register(
        AssetRegisterIn(filename=name, path=str(path), type="image", tags=tags or [], **overrides)
    )


def _beat(id="b1", order=1, asset_id=None, visual_hint=None, narration="hello", duration=2.0) -> Beat:
    return Beat(id=id, order=order, type=BeatType.BODY, narration=narration, duration=duration, visual_hint=visual_hint, asset_id=asset_id)


class ComputeAssetConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service, self.db, self.engine = _asset_service_with(self.tmp_path)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_no_hint_or_narration_is_high_confidence(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg", tags=["mountain"])
        beat = _beat(narration=None, visual_hint=None)
        self.assertEqual(compute_asset_confidence(beat, asset), "HIGH")

    def test_strong_tag_overlap_is_high_confidence(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg", tags=["woman", "gift", "surprise"])
        beat = _beat(visual_hint="woman opening a gift, surprise")
        self.assertEqual(compute_asset_confidence(beat, asset), "HIGH")

    def test_partial_overlap_is_medium_confidence(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg", tags=["woman"])
        beat = _beat(visual_hint="woman opening a mysterious ancient chest slowly")
        self.assertEqual(compute_asset_confidence(beat, asset), "MEDIUM")

    def test_zero_overlap_is_low_confidence(self):
        asset = _register(self.service, self.tmp_path, "mountain_sunrise.jpg", tags=["mountain", "sunrise"])
        beat = _beat(visual_hint="woman opening a gift with surprise")
        self.assertEqual(compute_asset_confidence(beat, asset), "LOW")

    def test_filename_tokens_also_count_toward_overlap(self):
        asset = _register(self.service, self.tmp_path, "woman_gift_surprise.jpg", tags=[])
        beat = _beat(visual_hint="woman opening a gift, surprise")
        self.assertEqual(compute_asset_confidence(beat, asset), "HIGH")

    def test_punctuation_in_narration_does_not_break_matching(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg", tags=["home"])
        beat = _beat(visual_hint=None, narration="Home.")
        # "Home." (with trailing punctuation) must still match the "home"
        # tag -- if punctuation weren't stripped, the token would be
        # "home" only after Path().stem strips it as a fake extension,
        # which is exactly the fragile behavior this dedicated prose
        # tokenizer avoids relying on.
        self.assertEqual(compute_asset_confidence(beat, asset), "HIGH")

    def test_ai_generated_asset_is_always_high_confidence_despite_zero_overlap(self):
        # Task 59 -- see docs/features/59-ai-image-generation.md. An
        # AI-generated image has no tags/filename overlap with the beat's
        # own visual_hint by construction (see imagegen_generate.py's own
        # AssetRegisterIn call) -- without this override, every single
        # "Generate Full by AI" project would score LOW here, permanently
        # stuck at NEEDS_REVIEW (any warning forces that status -- see
        # quality.analyzer's own status logic) with no user action able to
        # raise a generated image's own "confidence".
        asset = _register(
            self.service, self.tmp_path, "beat_beat_01.png", tags=[], source="ai_image_generator",
        )
        beat = _beat(visual_hint="a lighthouse keeper watching a storm over dark water")
        self.assertEqual(compute_asset_confidence(beat, asset), "HIGH")


class ResolveBeatAssetInfoTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service, self.db, self.engine = _asset_service_with(self.tmp_path)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_no_asset_id_has_no_asset(self):
        info = _resolve_beat_asset_info(_beat(asset_id=None), self.service)
        self.assertFalse(info.has_asset)
        self.assertFalse(info.asset_valid)

    def test_unknown_asset_id_is_invalid(self):
        info = _resolve_beat_asset_info(_beat(asset_id=999999), self.service)
        self.assertTrue(info.has_asset)
        self.assertFalse(info.asset_valid)

    def test_missing_file_is_invalid(self):
        asset = _register(self.service, self.tmp_path, "gone.jpg")
        Path(asset.path).unlink()
        info = _resolve_beat_asset_info(_beat(asset_id=asset.id), self.service)
        self.assertTrue(info.has_asset)
        self.assertFalse(info.asset_valid)

    def test_active_asset_is_valid_with_confidence_and_suitability(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg", tags=["woman"], width=1080, height=1920)
        info = _resolve_beat_asset_info(_beat(asset_id=asset.id, visual_hint="a woman"), self.service)
        self.assertTrue(info.asset_valid)
        self.assertEqual(info.asset_confidence, "HIGH")
        self.assertEqual(info.portrait_suitability, "EXCELLENT")

    def test_invalid_status_asset_is_not_valid(self):
        asset = _register(self.service, self.tmp_path, "photo.jpg")
        asset.status = "INVALID"
        self.db.commit()
        info = _resolve_beat_asset_info(_beat(asset_id=asset.id), self.service)
        self.assertFalse(info.asset_valid)

    def test_ai_generated_asset_skips_low_resolution_classification(self):
        # Task 59: gpt-image-1-mini's own portrait size (1024x1536) is
        # genuinely short of a 1080x1920 render profile's "cover" scale
        # (see classify_portrait_suitability) -- a fixed, accepted property
        # of the chosen model, not a variable curation-quality problem a
        # human can fix by picking a different local photo. None here (not
        # "LOW_RESOLUTION") reuses the analyzer's own existing "no data =
        # no penalty" rule rather than flagging every beat of every
        # AI-generated project as an unresolvable, permanent review item.
        asset = _register(
            self.service, self.tmp_path, "beat_beat_01.png",
            source="ai_image_generator", width=1024, height=1536,
        )
        info = _resolve_beat_asset_info(_beat(asset_id=asset.id), self.service)
        self.assertIsNone(info.portrait_suitability)

    def test_non_ai_asset_still_gets_real_low_resolution_classification(self):
        # Confirms the Task 59 exemption above is scoped to
        # source="ai_image_generator" only -- an ordinary library asset at
        # the exact same dimensions is still flagged, unchanged.
        asset = _register(
            self.service, self.tmp_path, "small_photo.jpg", width=1024, height=1536,
        )
        info = _resolve_beat_asset_info(_beat(asset_id=asset.id), self.service)
        self.assertEqual(info.portrait_suitability, "LOW_RESOLUTION")


class RunQualityCheckIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service, self.db, self.engine = _asset_service_with(self.tmp_path)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_fully_assigned_plan_is_ready(self):
        assets = [
            _register(self.service, self.tmp_path, f"beat{i}.jpg", tags=["story"], width=1080, height=1920)
            for i in range(1, 4)
        ]
        types = [BeatType.HOOK, BeatType.BUILD, BeatType.ENDING]  # varied -- 3x the same purpose would itself warn
        beats = [
            Beat(
                id=f"b{i}", order=i, type=types[i - 1], asset_id=assets[i - 1].id,
                narration=f"Distinct narration {i}.", duration=2.0,
            )
            for i in range(1, 4)
        ]
        report = run_quality_check(beats, BeatPlan(beats=beats).config, self.service)
        self.assertEqual(report.status, "READY")

    def test_missing_asset_blocks(self):
        asset = _register(self.service, self.tmp_path, "beat1.jpg", width=1080, height=1920)
        beats = [
            _beat(id="b1", order=1, asset_id=asset.id, narration="one"),
            _beat(id="b2", order=2, asset_id=None, narration="two"),
        ]
        report = run_quality_check(beats, BeatPlan(beats=beats).config, self.service)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("MISSING_VISUAL_ASSET", [i.code for i in report.issues])


class QualityCheckEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_check_plan_quality_endpoint(self):
        service = AssetService(self.db)
        asset = _register(service, self.tmp_path, "beat1.jpg", width=1080, height=1920)
        beats = [_beat(id="b1", order=1, asset_id=asset.id, narration="hello there")]
        plan = BeatPlan(beats=beats)
        report = check_plan_quality(QualityCheckRequest(plan=plan), self.db)
        self.assertIn(report.status, ("READY", "NEEDS_REVIEW", "BLOCKED"))
        self.assertIsInstance(report.score, int)

    def test_check_project_quality_endpoint_uses_saved_project_draft(self):
        project_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=project_engine, tables=[Project.__table__])
        ProjectSessionLocal = sessionmaker(bind=project_engine)

        with patch("app.modules.beat.project_service.SessionLocal", ProjectSessionLocal):
            from app.modules.beat.project_service import create_project
            from app.modules.beat.schemas import ProjectConfig

            project_id = create_project("My Project", "Some script.", ProjectConfig())
            with tempfile.TemporaryDirectory() as tmp_dir:
                # A real Settings instance, not FastAPI's own unresolved
                # Depends(get_settings) sentinel -- this test calls the
                # route handler directly as a plain function (this file's
                # own established convention, see module docstring), which
                # never triggers FastAPI's dependency injection. Task 24's
                # own project-level (always-invoked, even for zero beats)
                # _resolve_audio_master_flags is the first caller in this
                # chain to actually *read* settings.library_dir rather than
                # merely accept the parameter -- Task 23's own per-beat
                # motion check never surfaced this because it short-circuits
                # before touching settings whenever a beat has no asset_id,
                # which this test's own zero-beat project always satisfies.
                report = check_project_quality(project_id, mode="NORMAL", db=self.db, settings=Settings(library_dir=tmp_dir))
            # A freshly-created project has zero beats -- a real, valid
            # pre-"Generate Beats" state (section 32: "no beats yet" is a
            # legitimate lifecycle state, not an HTTP error).
            self.assertEqual(report.status, "BLOCKED")
            self.assertIn("NO_BEATS", [i.code for i in report.issues])

        project_engine.dispose()


if __name__ == "__main__":
    unittest.main()
