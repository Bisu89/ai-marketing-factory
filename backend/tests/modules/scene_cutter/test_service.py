"""Tests for SceneCutterService._merge_short_scenes -- real user report:
a single continuous scene came back cut into 3. Pure, in-memory tests
against real scenedetect.FrameTimecode instances (no video file/OpenCV
involved -- the merge itself only ever operates on (start, end) tuples).
"""

import unittest
from pathlib import Path

from scenedetect import FrameTimecode

from app.modules.scene_cutter.service import SceneCutterService

FPS = 30.0


def _tc(seconds: float) -> FrameTimecode:
    return FrameTimecode(timecode=seconds, fps=FPS)


class MergeShortScenesTests(unittest.TestCase):
    def test_short_scene_merges_into_the_one_before_it(self):
        scenes = [
            (_tc(0.0), _tc(3.0)),
            (_tc(3.0), _tc(3.4)),  # 0.4s -- a spurious flash/whip-pan
            (_tc(3.4), _tc(7.0)),
        ]
        merged = SceneCutterService._merge_short_scenes(scenes, min_duration_sec=1.0)

        # Only the short scene absorbs into its predecessor (shifting the
        # boundary from 3.0 to 3.4) -- the trailing 3.6s scene is
        # legitimately long on its own and stays a separate scene.
        self.assertEqual(merged, [(_tc(0.0), _tc(3.4)), (_tc(3.4), _tc(7.0))])

    def test_no_merge_when_every_scene_is_already_long_enough(self):
        scenes = [(_tc(0.0), _tc(3.0)), (_tc(3.0), _tc(6.0)), (_tc(6.0), _tc(9.0))]
        merged = SceneCutterService._merge_short_scenes(scenes, min_duration_sec=1.0)
        self.assertEqual(merged, scenes)

    def test_short_opening_scene_is_never_merged_forward(self):
        # No predecessor to absorb it into -- left as-is, same edge case
        # _merge_short_beats already accepts for a short opening beat.
        scenes = [(_tc(0.0), _tc(0.5)), (_tc(0.5), _tc(4.0))]
        merged = SceneCutterService._merge_short_scenes(scenes, min_duration_sec=1.0)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0], (_tc(0.0), _tc(0.5)))

    def test_multiple_consecutive_short_scenes_all_absorb_into_the_same_predecessor(self):
        scenes = [
            (_tc(0.0), _tc(3.0)),
            (_tc(3.0), _tc(3.3)),
            (_tc(3.3), _tc(3.6)),
            (_tc(3.6), _tc(8.0)),  # 4.4s -- legitimately long, stays separate
        ]
        merged = SceneCutterService._merge_short_scenes(scenes, min_duration_sec=1.0)
        self.assertEqual(merged, [(_tc(0.0), _tc(3.6)), (_tc(3.6), _tc(8.0))])

    def test_single_scene_list_is_returned_unchanged(self):
        scenes = [(_tc(0.0), _tc(2.0))]
        merged = SceneCutterService._merge_short_scenes(scenes, min_duration_sec=1.0)
        self.assertEqual(merged, scenes)

    def test_empty_scene_list_is_returned_unchanged(self):
        self.assertEqual(SceneCutterService._merge_short_scenes([], min_duration_sec=1.0), [])


class PreviewScenesTests(unittest.TestCase):
    """docs/features/107-scene-cutter-false-split-fix.md's Preview follow-up
    -- only the input-resolution/error-surfacing half is covered here
    (no OpenCV/real video decoding, no DB session for the video_id branch);
    the detection call itself is the same _detect_scenes already exercised
    manually end to end and covered by MergeShortScenesTests above.
    """

    def test_missing_source_path_raises_value_error(self):
        service = SceneCutterService(library_dir=Path("."))
        with self.assertRaises(ValueError):
            service.preview_scenes(
                video_id=None, source_path="Z:/definitely/does/not/exist.mp4",
                threshold=60.0, min_scene_len_sec=1.2, trim_sec=0.0,
            )


if __name__ == "__main__":
    unittest.main()
