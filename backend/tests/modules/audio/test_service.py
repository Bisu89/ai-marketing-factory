import unittest

from app.modules.audio.schemas import BgmCandidate
from app.modules.audio.service import select_bgm


def _candidate(asset_id: int, tags: list[str] | None = None) -> BgmCandidate:
    return BgmCandidate(asset_id=asset_id, path=f"track_{asset_id}.wav", duration_sec=30.0, tags=tags or [])


class SelectBgmTests(unittest.TestCase):
    def test_empty_candidates_returns_none(self):
        self.assertIsNone(select_bgm([], "warm and reflective", seed=1))

    def test_same_inputs_always_select_the_same_candidate(self):
        candidates = [_candidate(1, ["piano"]), _candidate(2, ["piano"]), _candidate(3, ["piano"])]
        first = select_bgm(candidates, "warm and reflective", seed=7)
        second = select_bgm(candidates, "warm and reflective", seed=7)
        self.assertEqual(first.asset_id, second.asset_id)

    def test_tone_keyword_matches_tagged_candidate_over_untagged(self):
        candidates = [
            _candidate(1, ["upbeat", "happy"]),
            _candidate(2, ["piano", "soft", "emotional"]),
        ]
        picked = select_bgm(candidates, "warm and reflective, emotional story", seed=0)
        self.assertEqual(picked.asset_id, 2)

    def test_no_tone_match_falls_back_to_rotation_not_a_fixed_default(self):
        candidates = [_candidate(1), _candidate(2), _candidate(3)]
        picks = [select_bgm(candidates, None, seed=s).asset_id for s in range(1, 4)]
        self.assertEqual(len(set(picks)), 3)  # all three distinct -- real rotation, not always the same track

    def test_rotation_matches_the_briefs_own_worked_example_shape(self):
        # Section 36's own example: project 01/02/03/04 -> track 1/2/3/1
        # (wrapping). Using project id directly as the seed reproduces this
        # exactly for a 3-track library.
        candidates = [_candidate(1), _candidate(2), _candidate(3)]
        picks = [select_bgm(candidates, None, seed=project_id).asset_id for project_id in range(1, 5)]
        self.assertEqual(picks[0], picks[3])  # project 1 and project 4 land on the same track
        self.assertEqual(len(set(picks[:3])), 3)  # projects 1-3 each land on a different track

    def test_multiple_equally_tagged_tracks_still_rotate_by_seed(self):
        candidates = [_candidate(1, ["piano", "soft"]), _candidate(2, ["piano", "soft"])]
        picks = {select_bgm(candidates, "emotional", seed=s).asset_id for s in range(4)}
        self.assertEqual(picks, {1, 2})  # both tracks get used across different seeds, not just one

    def test_retry_of_the_same_project_selects_the_same_track(self):
        # Section 37's own explicit "a retry of the same project should
        # select the same BGM unless the user explicitly requests a new
        # variation" -- same candidate list + same seed (project id) across
        # two independent calls (simulating a retry) must agree.
        candidates = [_candidate(1, ["ambient"]), _candidate(2, ["ambient"]), _candidate(3, ["ambient"])]
        first_attempt = select_bgm(candidates, "documentary", seed=42)
        second_attempt = select_bgm(candidates, "documentary", seed=42)
        self.assertEqual(first_attempt.asset_id, second_attempt.asset_id)


if __name__ == "__main__":
    unittest.main()
