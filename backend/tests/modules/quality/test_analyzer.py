"""Tests for app.modules.quality.analyzer (Task 16 -- see
docs/features/42-content-quality-gate.md). Pure functions, no DB/FFmpeg/AI
-- every test builds plain BeatAnalysisInput/QualityAnalysisInput objects
directly, matching app.modules.composition's own "pure contract" test
style (no ORM, no FastAPI TestClient anywhere in this suite).
"""

import unittest

from app.modules.quality.analyzer import (
    DIMENSION_WEIGHTS,
    NEEDS_REVIEW_THRESHOLD,
    READY_THRESHOLD,
    analyze_audio,
    analyze_captions,
    analyze_motion,
    analyze_narrative,
    analyze_pacing,
    analyze_visual,
    evaluate_readiness,
)
from app.modules.quality.schemas import (
    BeatAnalysisInput,
    BeatAssetInfo,
    ProjectAudioConfigInput,
    ProjectCaptionConfigInput,
    QualityAnalysisInput,
)


def _beat(
    id="b1", order=1, type="BODY", narration="Some real narration text.", duration=2.0,
    visual_hint=None, motion_preset=None, has_asset=True, asset_valid=True, confidence="HIGH",
    suitability="EXCELLENT",
) -> BeatAnalysisInput:
    return BeatAnalysisInput(
        id=id, order=order, type=type, narration=narration, duration=duration,
        visual_hint=visual_hint, motion_preset=motion_preset,
        asset=BeatAssetInfo(
            has_asset=has_asset,
            asset_valid=asset_valid,
            asset_confidence=confidence if asset_valid else None,
            portrait_suitability=suitability if asset_valid else None,
        ),
    )


def _beats(n: int, **overrides) -> list[BeatAnalysisInput]:
    return [_beat(id=f"b{i}", order=i, narration=f"Distinct narration number {i}.", **overrides) for i in range(1, n + 1)]


class NarrativeAnalysisTests(unittest.TestCase):
    def test_no_beats_is_blocking(self):
        score, issues = analyze_narrative([])
        self.assertEqual(score, 0)
        self.assertEqual([i.code for i in issues], ["NO_BEATS"])
        self.assertEqual(issues[0].severity, "error")

    def test_varied_purposes_no_diversity_warning(self):
        beats = [
            _beat(id="b1", order=1, type="HOOK", narration="one"),
            _beat(id="b2", order=2, type="SETUP", narration="two"),
            _beat(id="b3", order=3, type="REVEAL", narration="three"),
        ]
        score, issues = analyze_narrative(beats)
        self.assertNotIn("LOW_PURPOSE_DIVERSITY", [i.code for i in issues])
        self.assertEqual(score, 100)

    def test_all_same_purpose_flags_low_diversity(self):
        beats = [_beat(id=f"b{i}", order=i, type="HOOK", narration=f"n{i}") for i in range(1, 6)]
        score, issues = analyze_narrative(beats)
        codes = [i.code for i in issues]
        self.assertIn("LOW_PURPOSE_DIVERSITY", codes)
        self.assertLess(score, 100)

    def test_three_consecutive_same_purpose_flags_duplication(self):
        beats = [
            _beat(id="b1", order=1, type="SETUP", narration="a"),
            _beat(id="b2", order=2, type="SETUP", narration="b"),
            _beat(id="b3", order=3, type="SETUP", narration="c"),
            _beat(id="b4", order=4, type="REVEAL", narration="d"),
        ]
        score, issues = analyze_narrative(beats)
        dup_issues = [i for i in issues if i.code == "PURPOSE_DUPLICATION"]
        self.assertEqual(len(dup_issues), 1)
        self.assertIn("3 consecutive SETUP", dup_issues[0].message)

    def test_two_consecutive_same_purpose_does_not_flag(self):
        beats = [
            _beat(id="b1", order=1, type="SETUP", narration="a"),
            _beat(id="b2", order=2, type="SETUP", narration="b"),
            _beat(id="b3", order=3, type="REVEAL", narration="c"),
        ]
        _, issues = analyze_narrative(beats)
        self.assertNotIn("PURPOSE_DUPLICATION", [i.code for i in issues])

    def test_exact_duplicate_narration_detected(self):
        beats = [
            _beat(id="b1", order=1, narration="He came home."),
            _beat(id="b2", order=2, narration="He came home."),
            _beat(id="b3", order=3, narration="Something different."),
        ]
        score, issues = analyze_narrative(beats)
        dup = [i for i in issues if i.code == "DUPLICATE_NARRATION"]
        self.assertEqual(len(dup), 1)
        self.assertLess(score, 100)

    def test_duplicate_narration_normalizes_case_punctuation_whitespace(self):
        beats = [
            _beat(id="b1", order=1, narration="He came home."),
            _beat(id="b2", order=2, narration="  HE   came home  "),
        ]
        _, issues = analyze_narrative(beats)
        self.assertEqual([i.code for i in issues], ["DUPLICATE_NARRATION"])

    def test_distinct_narration_not_flagged(self):
        beats = _beats(3)
        _, issues = analyze_narrative(beats)
        self.assertNotIn("DUPLICATE_NARRATION", [i.code for i in issues])


class PacingAnalysisTests(unittest.TestCase):
    def test_no_beats(self):
        score, issues, metrics = analyze_pacing([])
        self.assertEqual((score, issues, metrics), (0, [], {}))

    def test_consistent_pacing_scores_high_no_warnings(self):
        beats = [_beat(id=f"b{i}", order=i, duration=2.0) for i in range(1, 6)]
        score, issues, metrics = analyze_pacing(beats)
        self.assertEqual(score, 100)
        self.assertEqual(issues, [])
        self.assertAlmostEqual(metrics["average"], 2.0)

    def test_extreme_outlier_flagged_and_lowers_score(self):
        # section 7's own literal example: 2.0, 4.2, 2.1, 2.0, 9.8
        durations = [2.0, 4.2, 2.1, 2.0, 9.8]
        beats = [_beat(id=f"b{i}", order=i, duration=d) for i, d in enumerate(durations, start=1)]
        score, issues, metrics = analyze_pacing(beats)
        outlier_codes = [i for i in issues if i.code == "PACING_OUTLIER"]
        self.assertGreaterEqual(len(outlier_codes), 1)
        self.assertLess(score, 100)
        # The beat itself is never rewritten -- analyze_pacing only reports.
        self.assertEqual(durations, [2.0, 4.2, 2.1, 2.0, 9.8])

    def test_moderate_variation_scores_between_extremes(self):
        consistent = [_beat(id=f"b{i}", order=i, duration=2.0) for i in range(1, 6)]
        moderate = [_beat(id=f"b{i}", order=i, duration=d) for i, d in enumerate([2.0, 3.0, 2.0, 3.5, 2.0], start=1)]
        extreme = [_beat(id=f"b{i}", order=i, duration=d) for i, d in enumerate([2.0, 4.2, 2.1, 2.0, 9.8], start=1)]
        consistent_score, _, _ = analyze_pacing(consistent)
        moderate_score, _, _ = analyze_pacing(moderate)
        extreme_score, _, _ = analyze_pacing(extreme)
        self.assertGreater(consistent_score, moderate_score)
        self.assertGreater(moderate_score, extreme_score)


class VisualAnalysisTests(unittest.TestCase):
    def test_no_beats(self):
        score, issues, metrics = analyze_visual([])
        self.assertEqual(score, 0)
        self.assertEqual(metrics.coverage, 0.0)

    def test_full_coverage_high_confidence_scores_100(self):
        beats = _beats(5)
        score, issues, metrics = analyze_visual(beats)
        self.assertEqual(score, 100)
        self.assertEqual(issues, [])
        self.assertEqual(metrics.coverage, 1.0)
        self.assertEqual(metrics.high_confidence, 5)

    def test_eighty_percent_coverage(self):
        beats = [_beat(id=f"b{i}", order=i, has_asset=(i != 5), asset_valid=(i != 5)) for i in range(1, 6)]
        score, issues, metrics = analyze_visual(beats)
        self.assertAlmostEqual(metrics.coverage, 0.8)
        self.assertEqual(metrics.missing, 1)
        self.assertIn("MISSING_VISUAL_ASSET", [i.code for i in issues])

    def test_missing_asset_id_is_missing_visual_asset(self):
        beats = [_beat(id="b1", order=1, has_asset=False, asset_valid=False)]
        _, issues, metrics = analyze_visual(beats)
        self.assertEqual([i.code for i in issues], ["MISSING_VISUAL_ASSET"])
        self.assertEqual(issues[0].beat_id, "b1")

    def test_asset_id_set_but_file_missing_is_missing_visual_file(self):
        beats = [_beat(id="b1", order=1, has_asset=True, asset_valid=False)]
        _, issues, metrics = analyze_visual(beats)
        self.assertEqual([i.code for i in issues], ["MISSING_VISUAL_FILE"])

    def test_low_confidence_flagged_as_warning_not_error(self):
        beats = [_beat(id="b1", order=1, confidence="LOW")]
        score, issues, metrics = analyze_visual(beats)
        low_issues = [i for i in issues if i.code == "LOW_VISUAL_CONFIDENCE"]
        self.assertEqual(len(low_issues), 1)
        self.assertEqual(low_issues[0].severity, "warning")
        self.assertEqual(metrics.low_confidence, 1)
        self.assertLess(score, 100)

    def test_low_resolution_flagged_as_warning(self):
        beats = [_beat(id="b1", order=1, suitability="LOW_RESOLUTION")]
        score, issues, metrics = analyze_visual(beats)
        res_issues = [i for i in issues if i.code == "LOW_RESOLUTION_ASSET"]
        self.assertEqual(len(res_issues), 1)
        self.assertEqual(res_issues[0].severity, "warning")
        self.assertLess(score, 100)

    def test_landscape_crop_required_is_not_rejected_outright(self):
        # section 19: "Do not reject every landscape image. The renderer
        # can crop." -- CROP_REQUIRED must not produce an error-severity issue.
        beats = [_beat(id="b1", order=1, suitability="CROP_REQUIRED")]
        score, issues, metrics = analyze_visual(beats)
        self.assertEqual([i for i in issues if i.severity == "error"], [])
        self.assertGreater(score, 0)


class MotionAnalysisTests(unittest.TestCase):
    def test_explicit_motion_on_every_beat(self):
        beats = [_beat(id="b1", order=1, motion_preset="SLOW_PUSH_IN")]
        score, issues = analyze_motion(beats, default_motion_preset=None)
        self.assertEqual((score, issues), (100, []))

    def test_project_default_covers_beats_without_explicit_motion(self):
        beats = [_beat(id="b1", order=1, motion_preset=None)]
        score, issues = analyze_motion(beats, default_motion_preset="STATIC")
        self.assertEqual((score, issues), (100, []))

    def test_missing_both_explicit_and_default_is_blocking(self):
        beats = [_beat(id="b1", order=1, motion_preset=None)]
        score, issues = analyze_motion(beats, default_motion_preset=None)
        self.assertEqual([i.code for i in issues], ["MISSING_MOTION"])
        self.assertEqual(issues[0].severity, "error")
        self.assertLess(score, 100)


class AudioAnalysisTests(unittest.TestCase):
    def test_narration_enabled_and_present(self):
        beats = _beats(3)
        score, issues = analyze_audio(beats, ProjectAudioConfigInput(narration_enabled=True))
        self.assertEqual((score, issues), (100, []))

    def test_narration_enabled_but_missing_on_one_beat(self):
        beats = [_beat(id="b1", order=1, narration="hi"), _beat(id="b2", order=2, narration=None)]
        score, issues = analyze_audio(beats, ProjectAudioConfigInput(narration_enabled=True))
        self.assertEqual([i.code for i in issues], ["MISSING_NARRATION"])
        self.assertEqual(issues[0].beat_id, "b2")
        self.assertEqual(issues[0].severity, "error")
        self.assertLess(score, 100)

    def test_narration_enabled_but_missing_everywhere_is_invalid_config(self):
        beats = [_beat(id="b1", order=1, narration=None), _beat(id="b2", order=2, narration="")]
        _, issues = analyze_audio(beats, ProjectAudioConfigInput(narration_enabled=True))
        self.assertIn("INVALID_AUDIO_CONFIG", [i.code for i in issues])

    def test_narration_disabled_never_flagged_even_when_all_beats_are_silent(self):
        beats = [_beat(id="b1", order=1, narration=None), _beat(id="b2", order=2, narration=None)]
        score, issues = analyze_audio(beats, ProjectAudioConfigInput(narration_enabled=False))
        self.assertEqual((score, issues), (100, []))


class CaptionAnalysisTests(unittest.TestCase):
    def test_captions_disabled_always_ok(self):
        beats = [_beat(id="b1", order=1, narration=None)]
        score, issues = analyze_captions(beats, ProjectCaptionConfigInput(enabled=False, preset_valid=True))
        self.assertEqual((score, issues), (100, []))

    def test_captions_enabled_with_narration_is_ok(self):
        beats = _beats(2)
        score, issues = analyze_captions(beats, ProjectCaptionConfigInput(enabled=True, preset_valid=True))
        self.assertEqual((score, issues), (100, []))

    def test_captions_enabled_but_invalid_preset_is_blocking(self):
        beats = _beats(2)
        score, issues = analyze_captions(beats, ProjectCaptionConfigInput(enabled=True, preset_valid=False))
        self.assertEqual([i.code for i in issues], ["INVALID_CAPTION_CONFIG"])
        self.assertEqual(score, 0)

    def test_captions_enabled_but_no_narration_anywhere_is_blocking(self):
        beats = [_beat(id="b1", order=1, narration=None), _beat(id="b2", order=2, narration="")]
        score, issues = analyze_captions(beats, ProjectCaptionConfigInput(enabled=True, preset_valid=True))
        self.assertEqual([i.code for i in issues], ["INVALID_CAPTION_CONFIG"])


class ReadinessEvaluationTests(unittest.TestCase):
    def _ready_beats(self, n=5):
        types = ["HOOK", "SETUP", "BUILD", "REVEAL", "ENDING"]
        return [
            _beat(id=f"b{i}", order=i, type=types[(i - 1) % len(types)], narration=f"Unique narration {i}.")
            for i in range(1, n + 1)
        ]

    def test_all_good_plan_is_ready(self):
        analysis_input = QualityAnalysisInput(beats=self._ready_beats(), default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        self.assertEqual(report.status, "READY")
        self.assertGreaterEqual(report.score, READY_THRESHOLD)
        self.assertEqual(report.issues, [])

    def test_missing_asset_blocks_even_with_a_high_score(self):
        beats = self._ready_beats()
        beats[2] = _beat(id=beats[2].id, order=3, type=beats[2].type, narration=beats[2].narration, has_asset=False, asset_valid=False)
        analysis_input = QualityAnalysisInput(beats=beats, default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        self.assertEqual(report.status, "BLOCKED")
        self.assertIn("MISSING_VISUAL_ASSET", [i.code for i in report.issues])
        # The would-be score without the blocker is high -- the blocker
        # must win regardless (section 25/42's own "score=95, missing
        # asset -> BLOCKED" example).
        self.assertGreaterEqual(report.score, 70)

    def test_low_confidence_asset_yields_needs_review_not_blocked(self):
        # A single weak-match beat barely moves a 6-dimension weighted
        # average (section 45's own "Scenario C" -- one low-confidence
        # swap in an otherwise-good 5-beat plan) -- READY requires a
        # *clean* plan, so any real warning at all means at least
        # NEEDS_REVIEW, never silently swallowed into a near-100 score.
        beats = self._ready_beats()
        beats[2] = _beat(id=beats[2].id, order=3, type=beats[2].type, narration=beats[2].narration, confidence="LOW", suitability="LOW_RESOLUTION")
        analysis_input = QualityAnalysisInput(beats=beats, default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        self.assertEqual(report.status, "NEEDS_REVIEW")
        self.assertEqual(report.issues, [])  # never a blocker on its own
        self.assertTrue(any(w.code == "LOW_VISUAL_CONFIDENCE" for w in report.warnings))

    def test_pacing_outlier_alone_is_a_warning_not_a_blocker(self):
        beats = self._ready_beats()
        beats[4] = _beat(id=beats[4].id, order=5, type=beats[4].type, narration=beats[4].narration, duration=20.0)
        analysis_input = QualityAnalysisInput(beats=beats, default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        self.assertNotEqual(report.status, "BLOCKED")
        self.assertTrue(any(w.code == "PACING_OUTLIER" for w in report.warnings))

    def test_no_beats_is_blocked(self):
        analysis_input = QualityAnalysisInput(beats=[], default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        self.assertEqual(report.status, "BLOCKED")
        self.assertEqual(report.score, 0)

    def test_strict_mode_escalates_needs_review_to_blocked(self):
        beats = self._ready_beats()
        beats[2] = _beat(id=beats[2].id, order=3, type=beats[2].type, narration=beats[2].narration, confidence="LOW", suitability="LOW_RESOLUTION")
        normal_report = evaluate_readiness(QualityAnalysisInput(beats=beats, default_motion_preset="STATIC", mode="NORMAL"))
        strict_report = evaluate_readiness(QualityAnalysisInput(beats=beats, default_motion_preset="STATIC", mode="STRICT"))
        self.assertEqual(normal_report.status, "NEEDS_REVIEW")
        self.assertEqual(strict_report.status, "BLOCKED")

    def test_dimensions_are_all_separately_visible(self):
        analysis_input = QualityAnalysisInput(beats=self._ready_beats(), default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        for key in DIMENSION_WEIGHTS:
            self.assertIsInstance(getattr(report.dimensions, key), int)

    def test_score_is_deterministic_across_repeated_calls(self):
        beats = self._ready_beats()
        scores = {evaluate_readiness(QualityAnalysisInput(beats=beats, default_motion_preset="STATIC")).score for _ in range(20)}
        self.assertEqual(len(scores), 1)

    def test_overall_score_is_the_documented_weighted_sum(self):
        analysis_input = QualityAnalysisInput(beats=self._ready_beats(), default_motion_preset="STATIC")
        report = evaluate_readiness(analysis_input)
        expected = round(sum(getattr(report.dimensions, k) * w for k, w in DIMENSION_WEIGHTS.items()))
        self.assertEqual(report.score, max(0, min(100, expected)))


if __name__ == "__main__":
    unittest.main()
