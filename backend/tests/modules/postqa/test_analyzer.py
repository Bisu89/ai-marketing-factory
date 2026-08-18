"""Pure tests for app.modules.postqa.analyzer (Task 28 -- see
docs/features/54-final-qa.md). No I/O -- every test builds its own QAInput
by hand and asserts on the returned QACheck list, mirroring
tests.modules.quality's own "pure contract" test shape.
"""

import unittest

from app.modules.postqa.analyzer import (
    check_audio_levels,
    check_beat_completeness,
    check_captions,
    check_dependency_freshness,
    check_final_video,
    check_metadata,
    check_package_complete,
    check_package_version,
    check_thumbnail,
    evaluate_final_qa,
    overall_status,
    score_from_checks,
)
from app.modules.postqa.schemas import (
    AudioLevelInfo,
    BeatCompletenessInfo,
    CaptionsInfo,
    DependencyFreshnessInfo,
    MetadataInfo,
    QAInput,
    ThumbnailInfo,
    VersionInfo,
    VideoStreamInfo,
)


def _clean_input(**overrides) -> QAInput:
    base = dict(
        project_id=1, package_exists=True, package_error_message=None,
        video=VideoStreamInfo(
            duration=10.0, width=1080, height=1920, fps=30.0, video_streams=1, audio_streams=1,
            video_codec="h264", audio_codec="aac", pix_fmt="yuv420p", file_exists=True, file_size=1234,
        ),
        expected_width=1080, expected_height=1920, expected_fps=30.0, expected_duration=10.0,
        audio_level=AudioLevelInfo(mean_volume_db=-20.0, max_volume_db=-3.0, probed=True),
        narration_enabled=True,
        thumbnail=ThumbnailInfo(
            exists=True, width=1080, height=1920, expected_width=1080, expected_height=1920,
            file_size=5678, is_low_quality=False,
        ),
        metadata=MetadataInfo(
            exists=True, parses=True, title="A great title", description="A great description.",
            hashtags=["#a", "#b"], referenced_video="final.mp4", referenced_thumbnail="thumbnail.jpg",
        ),
        captions=CaptionsInfo(enabled=True, exists=True, parses=True, dialogue_count=3, max_end_time=9.5),
        beats=BeatCompletenessInfo(total_beats=3, beats_with_motion_artifact=3, order_is_contiguous=True),
        dependencies=DependencyFreshnessInfo(audio_master_is_newer_than_video=False, captions_is_newer_than_video=False),
        version=VersionInfo(package_engine_version="post-package-v1", current_package_engine_version="post-package-v1"),
    )
    base.update(overrides)
    return QAInput(**base)


class PackageCompleteTests(unittest.TestCase):
    def test_complete_package_passes(self):
        check = check_package_complete(_clean_input())
        self.assertEqual(check.status, "PASS")

    def test_incomplete_package_fails_with_repair_stage_package(self):
        check = check_package_complete(_clean_input(package_exists=False, package_error_message="no video yet"))
        self.assertEqual(check.status, "FAIL")
        self.assertEqual(check.repair_stage, "PACKAGE")
        self.assertIn("no video yet", check.message)


class FinalVideoTests(unittest.TestCase):
    def test_all_checks_pass_for_a_clean_video(self):
        checks = check_final_video(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))
        self.assertEqual(len(checks), 5)  # exists, streams, resolution, fps, duration

    def test_missing_video_fails_and_short_circuits(self):
        video = VideoStreamInfo(
            duration=0.0, width=0, height=0, fps=0.0, video_streams=0, audio_streams=0,
            video_codec=None, audio_codec=None, pix_fmt=None, file_exists=False, file_size=0,
        )
        checks = check_final_video(_clean_input(video=video))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].code, "FINAL_VIDEO_MISSING")
        self.assertEqual(checks[0].status, "FAIL")
        self.assertEqual(checks[0].repair_stage, "RENDER")

    def test_empty_video_file_fails_and_short_circuits(self):
        video = VideoStreamInfo(
            duration=0.0, width=0, height=0, fps=0.0, video_streams=0, audio_streams=0,
            video_codec=None, audio_codec=None, pix_fmt=None, file_exists=True, file_size=0,
        )
        checks = check_final_video(_clean_input(video=video))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].code, "FINAL_VIDEO_INVALID")

    def test_wrong_stream_counts_fails(self):
        video = VideoStreamInfo(
            duration=10.0, width=1080, height=1920, fps=30.0, video_streams=2, audio_streams=0,
            video_codec="h264", audio_codec=None, pix_fmt="yuv420p", file_exists=True, file_size=1234,
        )
        checks = check_final_video(_clean_input(video=video))
        stream_check = next(c for c in checks if c.code == "FINAL_STREAM_INVALID")
        self.assertEqual(stream_check.status, "FAIL")

    def test_resolution_mismatch_fails(self):
        checks = check_final_video(_clean_input(expected_width=720, expected_height=1280))
        res_check = next(c for c in checks if c.code == "FINAL_RESOLUTION_MISMATCH")
        self.assertEqual(res_check.status, "FAIL")
        self.assertEqual(res_check.repair_stage, "RENDER")

    def test_fps_within_tolerance_passes(self):
        checks = check_final_video(_clean_input(expected_fps=30.3))
        fps_check = next(c for c in checks if c.code == "FINAL_FPS_MISMATCH")
        self.assertEqual(fps_check.status, "PASS")

    def test_fps_outside_tolerance_fails(self):
        checks = check_final_video(_clean_input(expected_fps=25.0))
        fps_check = next(c for c in checks if c.code == "FINAL_FPS_MISMATCH")
        self.assertEqual(fps_check.status, "FAIL")

    def test_duration_within_tolerance_passes(self):
        checks = check_final_video(_clean_input(expected_duration=10.5))
        dur_check = next(c for c in checks if c.code == "FINAL_DURATION_MISMATCH")
        self.assertEqual(dur_check.status, "PASS")

    def test_duration_outside_tolerance_fails(self):
        checks = check_final_video(_clean_input(expected_duration=15.0))
        dur_check = next(c for c in checks if c.code == "FINAL_DURATION_MISMATCH")
        self.assertEqual(dur_check.status, "FAIL")
        self.assertEqual(dur_check.repair_stage, "RENDER")

    def test_no_expected_duration_skips_duration_check(self):
        checks = check_final_video(_clean_input(expected_duration=None))
        self.assertFalse(any(c.code == "FINAL_DURATION_MISMATCH" for c in checks))


class AudioLevelTests(unittest.TestCase):
    def test_narration_disabled_skips_entirely(self):
        checks = check_audio_levels(_clean_input(narration_enabled=False, audio_level=None))
        self.assertEqual(checks, [])

    def test_unprobed_audio_warns(self):
        checks = check_audio_levels(_clean_input(audio_level=AudioLevelInfo(None, None, False)))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "WARN")
        self.assertEqual(checks[0].code, "AUDIO_SILENT")

    def test_silent_audio_fails(self):
        checks = check_audio_levels(_clean_input(audio_level=AudioLevelInfo(-60.0, -55.0, True)))
        silence_check = next(c for c in checks if c.code == "AUDIO_SILENT")
        self.assertEqual(silence_check.status, "FAIL")
        self.assertEqual(silence_check.repair_stage, "AUDIO")

    def test_borderline_silence_threshold_passes(self):
        checks = check_audio_levels(_clean_input(audio_level=AudioLevelInfo(-49.9, -10.0, True)))
        silence_check = next(c for c in checks if c.code == "AUDIO_SILENT")
        self.assertEqual(silence_check.status, "PASS")

    def test_clipping_audio_warns_not_fails(self):
        checks = check_audio_levels(_clean_input(audio_level=AudioLevelInfo(-20.0, 0.0, True)))
        clip_check = next(c for c in checks if c.code == "AUDIO_CLIPPING")
        self.assertEqual(clip_check.status, "WARN")

    def test_clean_audio_passes_both_checks(self):
        checks = check_audio_levels(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))
        self.assertEqual(len(checks), 2)


class ThumbnailTests(unittest.TestCase):
    def test_missing_thumbnail_fails(self):
        checks = check_thumbnail(_clean_input(thumbnail=ThumbnailInfo(
            exists=False, width=None, height=None, expected_width=1080, expected_height=1920,
            file_size=0, is_low_quality=False,
        )))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].code, "THUMBNAIL_INVALID")
        self.assertEqual(checks[0].repair_stage, "THUMBNAIL")

    def test_wrong_dimensions_fails(self):
        checks = check_thumbnail(_clean_input(thumbnail=ThumbnailInfo(
            exists=True, width=100, height=100, expected_width=1080, expected_height=1920,
            file_size=100, is_low_quality=False,
        )))
        dims_check = next(c for c in checks if c.code == "THUMBNAIL_INVALID")
        self.assertEqual(dims_check.status, "FAIL")

    def test_low_quality_warns_not_fails(self):
        checks = check_thumbnail(_clean_input(thumbnail=ThumbnailInfo(
            exists=True, width=1080, height=1920, expected_width=1080, expected_height=1920,
            file_size=100, is_low_quality=True,
        )))
        quality_check = next(c for c in checks if c.code == "THUMBNAIL_LOW_QUALITY")
        self.assertEqual(quality_check.status, "WARN")
        self.assertEqual(quality_check.repair_stage, "THUMBNAIL")

    def test_clean_thumbnail_passes_both_checks(self):
        checks = check_thumbnail(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))


class MetadataTests(unittest.TestCase):
    def test_missing_metadata_fails(self):
        check = check_metadata(_clean_input(metadata=None))
        self.assertEqual(check.status, "FAIL")
        self.assertEqual(check.repair_stage, "PACKAGE")

    def test_unparseable_metadata_fails(self):
        check = check_metadata(_clean_input(metadata=MetadataInfo(
            exists=True, parses=False, title=None, description=None, hashtags=None,
            referenced_video=None, referenced_thumbnail=None,
        )))
        self.assertEqual(check.status, "FAIL")

    def test_missing_title_fails(self):
        check = check_metadata(_clean_input(metadata=MetadataInfo(
            exists=True, parses=True, title="", description="A description.", hashtags=["#a"],
            referenced_video="final.mp4", referenced_thumbnail="thumbnail.jpg",
        )))
        self.assertEqual(check.status, "FAIL")

    def test_empty_hashtags_still_passes(self):
        # Task 27's own validate_package already treats an empty hashtag
        # list as a complete, valid package (see analyzer.py's own
        # check_metadata docstring) -- QA must agree, not invent a
        # stricter, disagreeing standard for the exact same package.
        check = check_metadata(_clean_input(metadata=MetadataInfo(
            exists=True, parses=True, title="A title", description="A description.", hashtags=[],
            referenced_video="final.mp4", referenced_thumbnail="thumbnail.jpg",
        )))
        self.assertEqual(check.status, "PASS")

    def test_missing_video_reference_fails(self):
        check = check_metadata(_clean_input(metadata=MetadataInfo(
            exists=True, parses=True, title="A title", description="A description.", hashtags=["#a"],
            referenced_video=None, referenced_thumbnail="thumbnail.jpg",
        )))
        self.assertEqual(check.status, "FAIL")

    def test_clean_metadata_passes(self):
        check = check_metadata(_clean_input())
        self.assertEqual(check.status, "PASS")


class CaptionsTests(unittest.TestCase):
    def test_disabled_captions_skip_entirely(self):
        checks = check_captions(_clean_input(captions=CaptionsInfo(
            enabled=False, exists=False, parses=False, dialogue_count=0, max_end_time=None,
        )))
        self.assertEqual(checks, [])

    def test_missing_captions_file_fails(self):
        checks = check_captions(_clean_input(captions=CaptionsInfo(
            enabled=True, exists=False, parses=False, dialogue_count=0, max_end_time=None,
        )))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].code, "CAPTIONS_INVALID")
        self.assertEqual(checks[0].repair_stage, "CAPTIONS")

    def test_zero_dialogue_lines_fails(self):
        checks = check_captions(_clean_input(captions=CaptionsInfo(
            enabled=True, exists=True, parses=True, dialogue_count=0, max_end_time=None,
        )))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].code, "CAPTIONS_INVALID")

    def test_caption_ending_after_video_duration_fails_timing(self):
        checks = check_captions(_clean_input(captions=CaptionsInfo(
            enabled=True, exists=True, parses=True, dialogue_count=3, max_end_time=20.0,
        )))
        timing_check = next(c for c in checks if c.code == "CAPTIONS_TIMING_INVALID")
        self.assertEqual(timing_check.status, "FAIL")
        self.assertEqual(timing_check.repair_stage, "CAPTIONS")

    def test_clean_captions_pass_both_checks(self):
        checks = check_captions(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))
        self.assertEqual(len(checks), 2)


class BeatCompletenessTests(unittest.TestCase):
    def test_zero_beats_fails(self):
        check = check_beat_completeness(_clean_input(beats=BeatCompletenessInfo(0, 0, True)))
        self.assertEqual(check.status, "FAIL")

    def test_non_contiguous_order_fails(self):
        check = check_beat_completeness(_clean_input(beats=BeatCompletenessInfo(3, 3, False)))
        self.assertEqual(check.status, "FAIL")

    def test_partial_motion_cache_warns_not_fails(self):
        check = check_beat_completeness(_clean_input(beats=BeatCompletenessInfo(3, 1, True)))
        self.assertEqual(check.status, "WARN")
        self.assertEqual(check.repair_stage, "MOTION")

    def test_fully_cached_beats_pass(self):
        check = check_beat_completeness(_clean_input())
        self.assertEqual(check.status, "PASS")


class DependencyFreshnessTests(unittest.TestCase):
    def test_stale_audio_fails(self):
        checks = check_dependency_freshness(_clean_input(dependencies=DependencyFreshnessInfo(True, False)))
        audio_check = next(c for c in checks if c.name == "dependency_freshness_audio")
        self.assertEqual(audio_check.status, "FAIL")
        self.assertEqual(audio_check.repair_stage, "RENDER")

    def test_stale_captions_fails(self):
        checks = check_dependency_freshness(_clean_input(dependencies=DependencyFreshnessInfo(False, True)))
        captions_check = next(c for c in checks if c.name == "dependency_freshness_captions")
        self.assertEqual(captions_check.status, "FAIL")

    def test_not_applicable_dependency_produces_no_check(self):
        checks = check_dependency_freshness(_clean_input(dependencies=DependencyFreshnessInfo(None, None)))
        self.assertEqual(checks, [])

    def test_fresh_dependencies_pass(self):
        checks = check_dependency_freshness(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))


class PackageVersionTests(unittest.TestCase):
    def test_no_recorded_version_warns(self):
        check = check_package_version(_clean_input(version=VersionInfo(None, "post-package-v1")))
        self.assertEqual(check.status, "WARN")

    def test_mismatched_version_warns_not_fails(self):
        check = check_package_version(_clean_input(version=VersionInfo("old-v0", "post-package-v1")))
        self.assertEqual(check.status, "WARN")
        self.assertEqual(check.repair_stage, "PACKAGE")

    def test_matching_version_passes(self):
        check = check_package_version(_clean_input())
        self.assertEqual(check.status, "PASS")


class EvaluateAndScoreTests(unittest.TestCase):
    def test_fully_clean_input_scores_100_and_passes(self):
        checks = evaluate_final_qa(_clean_input())
        self.assertTrue(all(c.status == "PASS" for c in checks))
        self.assertEqual(score_from_checks(checks), 100)
        self.assertEqual(overall_status(checks), "PASS")

    def test_a_single_warning_lowers_score_and_produces_pass_with_warnings(self):
        checks = evaluate_final_qa(_clean_input(thumbnail=ThumbnailInfo(
            exists=True, width=1080, height=1920, expected_width=1080, expected_height=1920,
            file_size=100, is_low_quality=True,
        )))
        self.assertEqual(overall_status(checks), "PASS_WITH_WARNINGS")
        self.assertLess(score_from_checks(checks), 100)

    def test_a_single_failure_always_produces_fail_regardless_of_score(self):
        # Section 45's own explicit requirement: one FAIL among many PASS
        # checks still yields an overall FAIL, even though the *score*
        # stays high -- score is informational only, never authoritative.
        checks = evaluate_final_qa(_clean_input(metadata=None))
        self.assertEqual(overall_status(checks), "FAIL")
        self.assertGreater(score_from_checks(checks), 0)

    def test_score_from_no_checks_is_zero(self):
        self.assertEqual(score_from_checks([]), 0)

    def test_overall_status_of_no_checks_is_pass(self):
        self.assertEqual(overall_status([]), "PASS")


if __name__ == "__main__":
    unittest.main()
