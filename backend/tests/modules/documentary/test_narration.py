"""Documentary narration (feature 166): segmenting, per-segment cache, retry
limits, budget/confirmation, master, ElevenLabs adapter (HTTP mocked)."""

import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from app.api.v1.endpoints import documentary_tts as tts_ep
from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.documentary import media
from app.modules.documentary import tts as tts_mod
from app.modules.documentary.models import DocumentaryScene, DocumentaryUsage
from app.modules.documentary.narration import NarrationPolicy, NarrationService, segment_scenes
from app.modules.documentary.tts import SynthResult, TTSBackend
from tests.modules.documentary import test_storyboard_assets as sb


def fake_scene(key, kind, text):
    return SimpleNamespace(scene_key=key, section_kind=kind, narration_text=text)


class SegmentingTests(unittest.TestCase):
    P = NarrationPolicy()

    def test_closes_at_section_change_and_size_limits(self):
        scenes = [fake_scene(f"S{i}", "hook", "x" * 200) for i in range(1, 4)] + [
            fake_scene("S4", "context", "y" * 200),
            fake_scene("S5", "context", "y" * 200),
        ]
        segs = segment_scenes(scenes, self.P)
        self.assertGreaterEqual(len(segs), 3)  # 600 hook chars exceed one segment, plus the context section
        for text, keys in segs:
            self.assertLessEqual(len(text), self.P.max_chars + 5)
        sections = [{s.section_kind for s in scenes if s.scene_key in keys} for _, keys in segs]
        self.assertTrue(all(len(x) == 1 for x in sections))  # never spans two sections

    def test_order_preserved_and_all_scenes_covered(self):
        scenes = [fake_scene(f"S{i}", "hook" if i < 6 else "context", "câu " * 40) for i in range(1, 12)]
        flat = [k for _, keys in segment_scenes(scenes, self.P) for k in keys]
        self.assertEqual(flat, [s.scene_key for s in scenes])

    def test_stub_is_merged_into_previous_in_same_section(self):
        scenes = [fake_scene("S1", "hook", "a" * 400), fake_scene("S2", "hook", "b" * 60)]
        segs = segment_scenes(scenes, self.P)
        self.assertEqual(len(segs), 1)


class _FlakyBackend(TTSBackend):
    """Counts calls; can fail or change its fingerprint on demand."""

    name = "flaky"
    extension = ".wav"

    def __init__(self):
        self.calls = 0
        self.fail = False
        self.voice = "v1"
        self.paid = False
        self.price_per_char = 0.0

    def fingerprint(self):
        return f"flaky:{self.voice}"

    def estimate_cost(self, chars):
        return None if self.price_per_char is None else chars * self.price_per_char

    def synthesize(self, text, out_path):
        self.calls += 1
        if self.fail:
            raise ExternalServiceError("provider down")
        media.make_silence(out_path, 1.0)
        return SynthResult(out_path, len(text), "m", self.voice, self.estimate_cost(len(text)))


class NarrationCase(sb._Case):
    def setUp(self):
        super().setUp()
        self.narr = NarrationService(self.db, self.root)
        self.flaky = _FlakyBackend()
        tts_mod.register_backend(self.flaky)
        self.addCleanup(lambda: tts_mod._REGISTRY.pop("flaky", None))

    def to_audio_ready(self):
        self.ready(hook_text=sentences_(14))
        for _ in range(3):
            self.svc.advance(self.p.id)
        for n, h in enumerate(self.assets.needing_images(self.p.id)):
            a, _ = self.assets.import_file(self.p.id, self.png(f"n{n}.png", (n, 5, 5)))
            self.assets.approve(self.p.id, a.id)
            self.assets.assign(self.p.id, h.id, a.id)
        self.svc.approve(self.p.id, "storyboard_assets")
        self.svc.advance(self.p.id)
        self.assertEqual(self.svc.get(self.p.id).state, "audio_ready")


def sentences_(n):
    return sb.sentences("Mở", n)


class PlanAndGenerateTests(NarrationCase):
    def test_generation_blocked_until_gate_three(self):
        self.ready()
        self.svc.plan_narration(self.p.id)
        with self.assertRaises(ValidationError):
            self.svc.generate_narration(self.p.id, "mock", None, False)

    def test_plan_needs_scenes(self):
        with self.assertRaises(ValidationError):
            self.narr.plan(self.p.id)

    def test_generate_measures_real_duration_and_logs_usage(self):
        self.to_audio_ready()
        info = self.svc.plan_narration(self.p.id)
        self.assertGreater(info["segments"], 1)
        res = self.svc.generate_narration(self.p.id, "mock", None, False)
        segs = self.narr.list(self.p.id)
        self.assertEqual(len(res["generated"]), len(segs))
        for s in segs:
            self.assertTrue(Path(s.audio_path).is_file())
            self.assertAlmostEqual(s.duration_sec, media.probe_duration(Path(s.audio_path)), places=2)
            self.assertTrue(self.narr.is_current(s))
        rows = self.db.query(DocumentaryUsage).filter_by(project_id=self.p.id).all()
        self.assertEqual(len(rows), len(segs))
        self.assertEqual(sum(r.chars for r in rows), sum(len(s.text) for s in segs))

    def test_unchanged_segments_are_cache_hits(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        n_rows = self.db.query(DocumentaryUsage).count()
        again = self.svc.generate_narration(self.p.id, "mock", None, False)
        self.assertEqual(again["generated"], [])
        self.assertEqual(again["skipped_cached"], len(self.narr.list(self.p.id)))
        self.assertEqual(self.db.query(DocumentaryUsage).count(), n_rows)  # nothing re-billed

    def test_editing_one_scene_regenerates_only_its_segment(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        before = {s.segment_key: (s.cache_key, s.audio_path) for s in self.narr.list(self.p.id)}
        scene = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        scene.narration_text += " Thêm một câu mới hoàn toàn."
        self.db.commit()
        info = self.svc.plan_narration(self.p.id)
        self.assertEqual(info["created"], 1)
        res = self.svc.generate_narration(self.p.id, "mock", None, False)
        self.assertEqual(len(res["generated"]), 1)
        after = {s.segment_key: (s.cache_key, s.audio_path) for s in self.narr.list(self.p.id)}
        untouched = [k for k in after if k in before and after[k] == before[k]]
        self.assertEqual(len(untouched), len(after) - 1)

    def test_changing_voice_marks_segments_stale(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertTrue(all(self.narr.is_current(s) for s in self.narr.list(self.p.id)))
        self.flaky.voice = "v2"
        self.assertFalse(any(self.narr.is_current(s) for s in self.narr.list(self.p.id)))
        codes = {i.code for i in self.narr.review(self.p.id)}
        self.assertEqual(codes, {"segment_not_ready"})

    def test_only_filter_and_unknown_key(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        first = self.narr.list(self.p.id)[0].segment_key
        res = self.svc.generate_narration(self.p.id, "mock", [first], False)
        self.assertEqual(res["generated"], [first])
        with self.assertRaises(ValidationError):
            self.svc.generate_narration(self.p.id, "mock", ["N999"], False)


class RetryBudgetTests(NarrationCase):
    def setUp(self):
        super().setUp()
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)

    def test_failure_is_recorded_and_retries_are_bounded(self):
        self.flaky.fail = True
        total = len(self.narr.list(self.p.id))
        for _ in range(3):
            res = self.svc.generate_narration(self.p.id, "flaky", None, False)
            self.assertEqual(len(res["failed"]), total)
        calls = self.flaky.calls
        res = self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertEqual(self.flaky.calls, calls)  # no 4th attempt against the provider
        self.assertIn("Đã thử 3 lần", res["failed"][0]["reason"])
        s = self.narr.list(self.p.id)[0]
        self.assertEqual((s.status, s.attempts), ("failed", 3))
        self.assertEqual(self.db.query(DocumentaryUsage).filter_by(ok=False).count(), total * 3)

    def test_recovery_after_provider_returns(self):
        self.flaky.fail = True
        self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.flaky.fail = False
        res = self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertEqual(res["failed"], [])
        self.assertTrue(all(self.narr.is_current(s) for s in self.narr.list(self.p.id)))

    def test_paid_backend_needs_explicit_confirmation(self):
        self.flaky.paid = True
        self.flaky.price_per_char = 0.001
        est = self.narr.estimate(self.p.id, "flaky")
        self.assertTrue(est["paid"])
        self.assertGreater(est["estimated_cost_usd"], 0)
        with self.assertRaises(ValidationError) as cm:
            self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertIn("confirm=true", str(cm.exception))
        self.assertEqual(self.flaky.calls, 0)  # nothing was spent
        self.svc.generate_narration(self.p.id, "flaky", None, True)
        self.assertGreater(self.flaky.calls, 0)

    def test_unknown_price_is_reported_not_guessed(self):
        self.flaky.paid = True
        self.flaky.price_per_char = None
        est = self.narr.estimate(self.p.id, "flaky")
        self.assertIsNone(est["estimated_cost_usd"])
        with self.assertRaises(ValidationError) as cm:
            self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertIn("chưa biết", str(cm.exception))
        self.svc.generate_narration(self.p.id, "flaky", None, True)
        spent, unknown = self.narr.spent_usd(self.p.id)
        self.assertEqual(spent, 0.0)
        self.assertEqual(unknown, len(self.narr.list(self.p.id)))  # ledger says "unknown", not "$0"

    def test_budget_blocks_until_confirmed(self):
        self.flaky.price_per_char = 0.01
        self.p.budget_usd = 0.5
        self.db.commit()
        with self.assertRaises(ValidationError) as cm:
            self.svc.generate_narration(self.p.id, "flaky", None, False)
        self.assertIn("ngân sách", str(cm.exception))
        self.assertEqual(self.flaky.calls, 0)


class MasterTests(NarrationCase):
    def test_master_offsets_cache_and_gate(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        with self.assertRaises(ValidationError):
            self.narr.build_master(self.p.id)  # nothing generated yet
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.assertIn("no_master", {i.code for i in self.narr.review(self.p.id)})
        m = self.narr.build_master(self.p.id)
        self.assertTrue(m["rebuilt"])
        segs = self.narr.list(self.p.id)
        self.assertEqual(segs[0].master_start, 0.0)
        for a, b in zip(segs, segs[1:]):
            self.assertAlmostEqual(b.master_start - a.master_end, self.narr.policy.gap_sec, places=2)
        self.assertAlmostEqual(m["duration_sec"], segs[-1].master_end, delta=0.1)
        self.assertFalse(self.narr.build_master(self.p.id)["rebuilt"])
        self.assertEqual(self.narr.review(self.p.id), [])
        # a regenerated segment makes the master stale again
        scene = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        scene.narration_text += " Câu bổ sung."
        self.db.commit()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.assertIn("no_master", {i.code for i in self.narr.review(self.p.id)})
        self.assertTrue(self.narr.build_master(self.p.id)["rebuilt"])

    def test_gate_four_requires_current_audio_and_master(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        with self.assertRaises(ValidationError):
            self.svc.approve(self.p.id, "narration_timing")
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        self.svc.approve(self.p.id, "narration_timing")

    def test_regenerating_narration_after_approval_revokes_it(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        self.svc.approve(self.p.id, "narration_timing")
        scene = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        scene.narration_text += " Câu mới."
        self.db.commit()
        self.svc.plan_narration(self.p.id)
        gate = next(g for g in self.svc.gate_statuses(self.svc.get(self.p.id)) if g.gate == "narration_timing")
        self.assertNotEqual(gate.status, "approved")


class ElevenLabsAdapterTests(unittest.TestCase):
    def settings(self, **kw):
        base = dict(elevenlabs_api_key="sk-secret", elevenlabs_voice_id="voice123", _env_file=None)
        base.update(kw)
        return Settings(**base)

    def response(self, status=200, payload=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = payload if payload is not None else {
            "audio_base64": base64.b64encode(b"ID3fakeaudio").decode(),
            "alignment": {
                "characters": list("Xin chào"),
                "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            },
        }
        return r

    def run_synth(self, settings, responses, tmp):
        b = tts_ep.ElevenLabsBackend()
        with patch.object(tts_ep, "get_settings", return_value=settings), patch.object(
            tts_ep.httpx, "post", side_effect=responses
        ) as post, patch.object(tts_ep.time, "sleep"):
            return b, post, b.synthesize("Xin chào", Path(tmp) / "a.mp3")

    def test_success_writes_audio_and_word_stamps(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            b, post, res = self.run_synth(self.settings(elevenlabs_usd_per_1k_chars=0.3), [self.response()], tmp)
            self.assertEqual(res.path.read_bytes(), b"ID3fakeaudio")
            self.assertEqual([(w.text, w.start, w.end) for w in res.word_stamps], [("Xin", 0.0, 0.3), ("chào", 0.4, 0.8)])
            self.assertEqual(res.cost_usd, round(len("Xin chào") / 1000 * 0.3, 6))
            kwargs = post.call_args.kwargs
            self.assertEqual(kwargs["headers"], {"xi-api-key": "sk-secret"})
            self.assertEqual(kwargs["json"]["model_id"], "eleven_multilingual_v2")
            self.assertIn("voice123", post.call_args.args[0])

    def test_unknown_price_gives_none_cost(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _, _, res = self.run_synth(self.settings(), [self.response()], tmp)
            self.assertIsNone(res.cost_usd)

    def test_missing_alignment_is_tolerated(self):
        import tempfile

        payload = {"audio_base64": base64.b64encode(b"abc").decode()}
        with tempfile.TemporaryDirectory() as tmp:
            _, _, res = self.run_synth(self.settings(), [self.response(payload=payload)], tmp)
            self.assertIsNone(res.word_stamps)

    def test_retries_429_then_succeeds_but_not_401(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            _, post, res = self.run_synth(self.settings(), [self.response(429), self.response(503), self.response()], tmp)
            self.assertEqual(post.call_count, 3)
            self.assertTrue(res.path.exists())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ExternalServiceError) as cm:
                self.run_synth(self.settings(), [self.response(401)], tmp)
            self.assertIn("401", str(cm.exception))
            self.assertNotIn("sk-secret", str(cm.exception))

    def test_network_error_never_leaks_key(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ExternalServiceError) as cm:
                self.run_synth(self.settings(), [httpx.ConnectError("boom sk-secret")] * 3, tmp)
            self.assertNotIn("sk-secret", str(cm.exception))

    def test_not_configured(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValidationError):
                self.run_synth(Settings(_env_file=None), [], tmp)

    def test_fingerprint_tracks_voice_settings_but_not_the_key(self):
        b = tts_ep.ElevenLabsBackend()
        with patch.object(tts_ep, "get_settings", return_value=self.settings()):
            f1 = b.fingerprint()
        with patch.object(tts_ep, "get_settings", return_value=self.settings(elevenlabs_api_key="other")):
            self.assertEqual(f1, b.fingerprint())
        with patch.object(tts_ep, "get_settings", return_value=self.settings(elevenlabs_stability=0.9)):
            self.assertNotEqual(f1, b.fingerprint())

    def test_char_alignment_to_words(self):
        w = tts_ep.words_from_char_alignment(list(" a  bc "), [0, 1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([(x.text, x.start, x.end) for x in w], [("a", 1, 2), ("bc", 4, 6)])

    def test_registered_and_paid(self):
        self.assertTrue(tts_mod.get_backend("elevenlabs").paid)
        self.assertFalse(tts_mod.get_backend("edge").paid)


if __name__ == "__main__":
    unittest.main()
