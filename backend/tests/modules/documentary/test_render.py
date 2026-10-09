"""Documentary render (feature 169): manifest, hash, preflight, quality check, jobs,
and one real (tiny) Remotion + ffmpeg render."""

import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ValidationError
from app.modules.documentary import media
from app.modules.documentary import render as render_mod
from app.modules.documentary.models import DocumentaryRenderJob, DocumentaryScene, DocumentarySceneTiming
from app.modules.documentary.render import RenderService, quality_check
from app.modules.documentary.render_plan import (
    FPS,
    REMOTION_DIR,
    RenderParams,
    build_manifest,
    claim_status_for,
    credit_text,
    cue_frame,
    date_context,
    derive_texts,
    proper_noun,
)
from tests.modules.documentary.test_timeline import TimelineCase

HAVE_TOOLCHAIN = bool(shutil.which("node") and shutil.which("npx") and shutil.which("ffmpeg") and (REMOTION_DIR / "node_modules").is_dir())


class DeriveTextTests(unittest.TestCase):
    def test_years_are_found_but_quantities_are_not(self):
        out = derive_texts("TimelineBuild", "Năm 1451 Mehmed lên ngôi, đến 1453 thành phố thất thủ; 2000 người chết.")
        self.assertEqual([(o["text"], o["role"]) for o in out], [("1451", "date"), ("1453", "date")])

    def test_big_number_with_unit_and_fallback(self):
        a = derive_texts("BigNumber", "Hơn 3 triệu người đã thiệt mạng.")
        self.assertEqual([o["text"] for o in a], ["3", "triệu người"])
        b = derive_texts("BigNumber", "Khoảng 80.000 quân Ottoman bao vây thành phố.")
        self.assertEqual([o["text"] for o in b], ["80.000", "quân Ottoman"])
        self.assertEqual(derive_texts("BigNumber", "Không có con số nào ở đây."), [])
        r = derive_texts("BigNumber", "Các nghiên cứu ước tính từ 50.000 đến 80.000 binh sĩ.")
        self.assertEqual([o["text"] for o in r], ["50.000–80.000", "binh sĩ"])  # a range stays a range

    def test_proper_nouns_are_capitalised_runs_not_lowercase_vietnamese(self):
        self.assertEqual(proper_noun("Quân đội tiến qua eo biển Bosphorus gần thành."), "Bosphorus")
        self.assertEqual(proper_noun("Năm 1432, Sultan Mehmed Đệ Nhị chào đời."), "Sultan Mehmed Đệ Nhị")
        self.assertIsNone(proper_noun("Họ đi về phía bắc rồi dừng lại."))

    def test_sentences_become_cards_and_nothing_is_invented(self):
        narr = "Biên niên sử ghi một con số. Ghi chép khác nói điều ngược lại. Khảo cổ chưa kết luận."
        out = derive_texts("EvidenceBoard", narr)
        self.assertEqual(len(out), 3)
        for o in out:
            self.assertIn(o["text"].rstrip("…"), narr)  # only text already in the narration
        long = "Một câu rất dài " * 20 + "."
        self.assertTrue(derive_texts("NewspaperStack", long)[0]["text"].endswith("…"))

    def test_dates_carry_the_words_around_them(self):
        n = "Constantinople là kinh đô của đế quốc từ năm 330. Suốt mười một thế kỷ, thành phố bị bao vây, nhưng chỉ bị chiếm vào năm 1204, trong cuộc Thập tự chinh thứ tư."
        out = derive_texts("TimelineBuild", n)
        self.assertEqual([(o["text"], o["sub"]) for o in out], [("330", "Constantinople là kinh đô của đế quốc"), ("1204", "trong cuộc Thập tự chinh thứ tư")])
        for o in out:
            self.assertIn(o["sub"], n)  # only words that are in the narration
        self.assertIsNone(date_context("1453.", 0, 4))

    def test_credit_text_policy(self):
        self.assertEqual(credit_text("ai_manual", None, None), "Minh họa AI")
        self.assertEqual(credit_text("ai_manual", None, None, "en"), "AI illustration")
        self.assertEqual(credit_text("archival", "CC BY 4.0", "Jane — Wikimedia Commons", "en"), "Image: Jane · CC BY 4.0")
        self.assertIsNone(credit_text("archival", "Public domain", "Bellini — Wikimedia Commons"))
        self.assertIsNone(credit_text("archival", "CC0", "X"))
        self.assertIsNone(credit_text("imported", None, None))
        self.assertEqual(credit_text("archival", "CC BY-SA 4.0", "Peter Riemann — Wikimedia Commons"), "Ảnh: Peter Riemann · CC BY-SA 4.0")

    def test_presets_without_derivable_text_stay_clean(self):
        self.assertEqual(derive_texts("PhotoKenBurns", "Bất kỳ lời dẫn nào."), [])

    def test_cue_follows_the_spoken_word_else_staggers(self):
        words = [["Thành", 10.0, 10.3, True], ["phố", 10.3, 10.6, True], ["1453,", 12.0, 12.5, True]]
        self.assertEqual(cue_frame("1453", words, 10.0, FPS, 0), 60)  # 2.0s into the scene
        self.assertEqual(cue_frame("không-có", words, 10.0, FPS, 2), 18)
        self.assertEqual(cue_frame("Thành", words, 10.5, FPS, 0), 0)  # never negative

    def test_claim_status_priority(self):
        st = {1: "verified", 2: "disputed", 3: "unverified"}
        self.assertEqual(claim_status_for([1], st), "verified")
        self.assertEqual(claim_status_for([1, 2], st), "disputed")
        self.assertEqual(claim_status_for([1, 3], st), "unverified")
        self.assertIsNone(claim_status_for([], st))


class ManifestCase(TimelineCase):
    def timeline_ready(self):
        tl = self.prepared()
        tl.align(self.p.id, "estimated")
        tl.assemble(self.p.id)
        return tl

    def params(self, **kw):
        return RenderParams(**{"kind": "preview", "scale": 0.5, **kw})

    def manifest(self, **kw):
        return build_manifest(self.db, self.root, self.p.id, self.params(**kw))


class ManifestTests(ManifestCase):
    def test_needs_a_timeline(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        with self.assertRaises(ValidationError):
            self.manifest()

    def test_scenes_tile_the_whole_video_with_no_gaps(self):
        self.timeline_ready()
        m, _public, _h = self.manifest()
        scenes = m["scenes"]
        self.assertEqual(scenes[0]["startFrame"], 0)
        for a, b in zip(scenes, scenes[1:]):
            self.assertEqual(a["startFrame"] + a["durationFrames"], b["startFrame"])  # no black gap, no overlap
        self.assertEqual(scenes[-1]["startFrame"] + scenes[-1]["durationFrames"], m["durationInFrames"])
        self.assertEqual((m["width"], m["height"], m["fps"]), (1920, 1080, 30))  # layout units never change; preview uses --scale

    def test_only_approved_images_are_included_and_copied_by_content_hash(self):
        self.timeline_ready()
        m, public, _ = self.manifest()
        used = {s["imageSrc"] for s in m["scenes"] if s["imageSrc"]}
        self.assertTrue(used)
        self.assertEqual(used, set(public))
        for rel, src in public.items():
            self.assertTrue(rel.startswith("images/") and src.is_file())
        prog = [s for s in m["scenes"] if s["preset"] in ("TimelineBuild", "BigNumber", "MapZoom", "EvidenceBoard", "HeadlineImpact")]
        self.assertTrue(all(s["imageSrc"] is None for s in prog))

    def test_every_preset_is_one_the_composition_knows(self):
        self.timeline_ready()
        m, _, _ = self.manifest()
        known = {"NewspaperStack", "ArchivalPortrait", "MapZoom", "TimelineBuild", "BigNumber", "EvidenceBoard", "PhotoKenBurns", "HeadlineImpact", "SplitComparison"}
        self.assertTrue({s["preset"] for s in m["scenes"]} <= known)

    def test_data_presets_with_nothing_to_show_fall_back_to_a_headline(self):
        """A timeline with no years would be an empty frame; it shows the narration's opening phrase."""
        self.timeline_ready()
        m, _, _ = self.manifest()
        timeline_scenes = [s for s in self.db.query(DocumentaryScene).filter_by(project_id=self.p.id) if s.visual_preset == "TimelineBuild"]
        self.assertTrue(timeline_scenes)  # the planner did choose TimelineBuild for the 'timeline' section
        by_key = {s["key"]: s for s in m["scenes"]}
        for sc in timeline_scenes:
            row = by_key[sc.scene_key]
            self.assertEqual(row["preset"], "HeadlineImpact")
            self.assertTrue(row["texts"])
        for row in m["scenes"]:
            if row["preset"] in ("TimelineBuild", "BigNumber", "MapZoom"):
                self.assertTrue(row["texts"], row["key"])  # never an empty data frame

    def test_user_choice_is_kept_when_the_user_wrote_the_text(self):
        self.timeline_ready()
        sc = next(s for s in self.db.query(DocumentaryScene).filter_by(project_id=self.p.id) if s.visual_preset == "TimelineBuild")
        sc.on_screen_text = [{"text": "1453", "role": "date"}]
        self.db.commit()
        row = {r["key"]: r for r in self.manifest()[0]["scenes"]}[sc.scene_key]
        self.assertEqual((row["preset"], row["texts"][0]["text"]), ("TimelineBuild", "1453"))

    def test_theme_is_part_of_the_manifest_and_the_hash(self):
        self.timeline_ready()
        m1, _, h1 = self.manifest()
        m2, _, h2 = self.manifest(theme="cinematic")
        self.assertEqual((m1["theme"], m2["theme"]), ("collage", "cinematic"))
        self.assertNotEqual(h1, h2)  # same data, different look -> different video, never a cache hit

    def test_image_aspect_is_reported_for_image_scenes_only(self):
        self.timeline_ready()
        m, _, _ = self.manifest()
        for row in m["scenes"]:
            if row["imageSrc"]:
                self.assertGreater(row["imageAspect"], 0)
            else:
                self.assertIsNone(row["imageAspect"])

    def test_music_changes_the_hash_and_is_validated_on_start(self):
        self.timeline_ready()
        tracks = Path(self.tmp.name) / "tracks"
        tracks.mkdir()
        a, b = tracks / "a.wav", tracks / "b.wav"
        tone(a, 1.0, freq=200)
        tone(b, 1.0, freq=300)
        h0 = self.manifest()[2]
        ha = self.manifest(music_path=str(a))[2]
        hb = self.manifest(music_path=str(b))[2]
        self.assertEqual(len({h0, ha, hb}), 3)  # no music / track A / track B are three different videos
        self.assertNotEqual(self.manifest(music_path=str(a), music_db=-18.0)[2], ha)
        with patch.object(render_mod, "_execute"):
            with self.assertRaises(ValidationError):
                RenderService(self.db, self.root).start(self.p.id, self.params(music_path="nope.mp3"))

    def test_unknown_theme_is_refused(self):
        self.timeline_ready()
        with patch.object(render_mod, "_execute"):
            with self.assertRaises(ValidationError):
                RenderService(self.db, self.root).start(self.p.id, self.params(theme="neon"))

    def _photo_scene(self):
        for sc in self.db.query(DocumentaryScene).filter_by(project_id=self.p.id).order_by(DocumentaryScene.order_index):
            if sc.visual_preset == "PhotoKenBurns" and sc.asset_id:
                return sc
        self.fail("no photo scene with an asset")

    def test_ai_images_are_labelled_and_attribution_licences_are_credited_automatically(self):
        self.timeline_ready()
        sc = self._photo_scene()
        asset = self.assets.get(self.p.id, sc.asset_id)
        asset.origin = "ai_manual"
        self.db.commit()
        row = {r["key"]: r for r in self.manifest()[0]["scenes"]}[sc.scene_key]
        self.assertIn(("Minh họa AI", "caption"), [(t["text"], t["role"]) for t in row["texts"]])
        asset.origin, asset.license, asset.attribution = "archival", "CC BY-SA 4.0", "Ann Author — Wikimedia Commons"
        self.db.commit()
        row = {r["key"]: r for r in self.manifest()[0]["scenes"]}[sc.scene_key]
        self.assertIn("Ảnh: Ann Author · CC BY-SA 4.0", [t["text"] for t in row["texts"]])
        asset.license = "Public domain"
        self.db.commit()
        row = {r["key"]: r for r in self.manifest()[0]["scenes"]}[sc.scene_key]
        self.assertEqual([t for t in row["texts"] if t["role"] in ("caption", "label")], [])  # nothing owed

    def test_auto_credit_never_duplicates_what_the_user_typed(self):
        self.timeline_ready()
        sc = self._photo_scene()
        asset = self.assets.get(self.p.id, sc.asset_id)
        asset.origin = "ai_manual"
        sc.on_screen_text = [{"text": "Tranh minh họa của tôi", "role": "caption"}]
        self.db.commit()
        row = {r["key"]: r for r in self.manifest()[0]["scenes"]}[sc.scene_key]
        self.assertEqual([t["text"] for t in row["texts"]], ["Tranh minh họa của tôi"])

    def test_user_text_overrides_derived_text(self):
        self.timeline_ready()
        sc = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        sc.on_screen_text = [{"text": "Tiêu đề do tôi viết", "role": "headline"}]
        self.db.commit()
        m, _, _ = self.manifest()
        first = m["scenes"][0]
        self.assertEqual([t["text"] for t in first["texts"]], ["Tiêu đề do tôi viết"])

    def test_subtitles_are_in_frames_and_ordered(self):
        self.timeline_ready()
        m, _, _ = self.manifest()
        subs = m["subtitles"]
        self.assertTrue(subs)
        self.assertTrue(all(s["endFrame"] > s["startFrame"] for s in subs))
        self.assertEqual([s["startFrame"] for s in subs], sorted(s["startFrame"] for s in subs))

    def test_hash_is_stable_and_tracks_every_real_input(self):
        self.timeline_ready()
        h1 = self.manifest()[2]
        self.assertEqual(self.manifest()[2], h1)  # deterministic
        self.assertNotEqual(self.manifest(scale=1.0)[2], h1)
        self.assertNotEqual(self.manifest(seconds=5)[2], h1)
        self.assertNotEqual(self.manifest(burn_subtitles=False)[2], h1)
        self.assertNotEqual(self.manifest(normalize_audio=False)[2], h1)
        # a hand edit of on-screen text changes the picture, so it must change the hash
        sc = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        sc.on_screen_text = [{"text": "Khác", "role": "headline"}]
        self.db.commit()
        self.assertNotEqual(self.manifest()[2], h1)

    def test_changing_one_scene_changes_only_its_manifest_entry(self):
        self.timeline_ready()
        before = {s["key"]: s for s in self.manifest()[0]["scenes"]}
        sc = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=2).one()
        sc.on_screen_text = [{"text": "Chỉ cảnh này đổi", "role": "headline"}]
        self.db.commit()
        after = {s["key"]: s for s in self.manifest()[0]["scenes"]}
        changed = [k for k in before if before[k] != after[k]]
        self.assertEqual(changed, [sc.scene_key])


class PreflightTests(ManifestCase):
    def test_tool_missing_and_unready_scene_are_named(self):
        self.timeline_ready()
        render = RenderService(self.db, self.root)
        with patch.object(render_mod, "tools", return_value={"node": None, "npx": None, "ffmpeg": "x", "ffprobe": "x"}):
            self.assertIn("missing_node", {i.code for i in render.preflight(self.p.id)})
        img = next(s for s in self.db.query(DocumentaryScene).filter_by(project_id=self.p.id) if s.asset_strategy == "image")
        asset = self.assets.get(self.p.id, img.asset_id)
        asset.approval_status = "rejected"
        self.db.commit()
        msgs = [i.message for i in render.preflight(self.p.id)]
        self.assertTrue(any(img.scene_key in m for m in msgs))

    def test_stale_timing_is_reported_per_scene(self):
        self.timeline_ready()
        row = self.db.query(DocumentarySceneTiming).filter_by(project_id=self.p.id).first()
        row.master_hash = "old"
        self.db.commit()
        issues = RenderService(self.db, self.root).preflight(self.p.id)
        self.assertTrue(any(i.code == "timing_stale" and row.scene_key in i.message for i in issues))


class StartTests(ManifestCase):
    def setUp(self):
        super().setUp()
        self.patcher = patch.object(render_mod, "_execute")  # no real render in these tests
        self.exec_mock = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.render = RenderService(self.db, self.root)

    def test_parameter_rules(self):
        self.timeline_ready()
        with self.assertRaises(ValidationError):
            self.render.start(self.p.id, RenderParams(kind="final", scale=0.5))
        with self.assertRaises(ValidationError):
            self.render.start(self.p.id, RenderParams(kind="final", scale=1.0, seconds=10))
        with self.assertRaises(ValidationError):
            self.render.start(self.p.id, RenderParams(kind="preview", scale=3.0))
        with self.assertRaises(ValidationError):
            self.render.start(self.p.id, RenderParams(kind="video"))

    def test_render_needs_gate_four(self):
        self.timeline_ready()
        with self.assertRaises(ValidationError) as cm:
            self.svc.start_render(self.p.id, self.params())
        self.assertIn("cổng 4", str(cm.exception))

    def test_job_is_queued_and_identical_request_is_reused(self):
        self.timeline_ready()
        job, reused = self.render.start(self.p.id, self.params())
        self.assertEqual((job.status, reused, job.kind), ("queued", False, "preview"))
        self.assertEqual(self.exec_mock.call_count, 1)
        render_mod._THREADS[job.id] = type("T", (), {"is_alive": lambda s: True})()  # the worker is still running
        self.addCleanup(render_mod._THREADS.pop, job.id, None)
        again, reused2 = self.render.start(self.p.id, self.params())
        self.assertEqual((again.id, reused2), (job.id, True))  # same inputs: same job, nothing started twice
        self.assertEqual(self.exec_mock.call_count, 1)
        other, reused3 = self.render.start(self.p.id, self.params(scale=0.25))
        self.assertNotEqual(other.id, job.id)
        self.assertFalse(reused3)

    def test_finished_identical_render_is_reused_but_missing_file_is_not(self):
        self.timeline_ready()
        job, _ = self.render.start(self.p.id, self.params())
        out = self.root / "fake.mp4"
        out.write_bytes(b"x")
        job.status, job.output_path = "succeeded", str(out)
        self.db.commit()
        again, reused = self.render.start(self.p.id, self.params())
        self.assertEqual((again.id, reused), (job.id, True))
        out.unlink()
        again2, reused2 = self.render.start(self.p.id, self.params())
        self.assertFalse(reused2)
        self.assertNotEqual(again2.id, job.id)

    def test_interrupted_job_is_marked_failed_not_left_running(self):
        self.timeline_ready()
        job, _ = self.render.start(self.p.id, self.params())
        job.status = "running"
        self.db.commit()
        self.assertEqual(self.render.get(self.p.id, job.id).status, "failed")
        self.assertIn("gián đoạn", self.render.get(self.p.id, job.id).error)

    def test_cancel_only_applies_to_active_jobs(self):
        self.timeline_ready()
        job, _ = self.render.start(self.p.id, self.params())
        render_mod._THREADS[job.id] = type("T", (), {"is_alive": lambda s: True})()
        self.render.cancel(self.p.id, job.id)
        self.assertIn(job.id, render_mod._CANCEL)
        render_mod._CANCEL.discard(job.id)
        job.status = "succeeded"
        self.db.commit()
        with self.assertRaises(ValidationError):
            self.render.cancel(self.p.id, job.id)

    def test_final_gate_needs_a_fresh_passing_final_render(self):
        self.timeline_ready()
        review = self.render.final_review(self.p.id)
        self.assertEqual(review.issues[0].code, "no_final_render")
        job, _ = self.render.start(self.p.id, RenderParams(kind="final", scale=1.0))
        out = self.root / "final.mp4"
        out.write_bytes(b"x")
        job.status, job.output_path, job.qc = "succeeded", str(out), {"ok": True, "issues": [], "warnings": [{"code": "timing_unverified", "message": "Cảnh S001: timing chưa xác nhận."}]}
        self.db.commit()
        review = self.render.final_review(self.p.id)
        self.assertTrue(review.ok, review.issues)
        self.assertEqual(len(review.warnings), 1)
        job.qc = {"ok": False, "issues": [{"code": "black_frames", "message": "Cảnh S003: có khung hình đen."}], "warnings": []}
        self.db.commit()
        self.assertEqual(self.render.final_review(self.p.id).issues[0].code, "black_frames")
        job.qc = {"ok": True, "issues": [], "warnings": []}
        sc = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        sc.on_screen_text = [{"text": "Đổi sau khi render", "role": "headline"}]
        self.db.commit()
        self.assertEqual(self.render.final_review(self.p.id).issues[0].code, "render_stale")


class RelativePathTests(unittest.TestCase):
    def test_remotion_gets_absolute_paths_even_when_the_library_dir_is_relative(self):
        """Regression from the first real run: './data/library' made Remotion (different cwd) fail with
        'neither valid JSON nor a file path'."""
        import tempfile
        from unittest.mock import MagicMock

        captured = {}

        class FakeProc:
            stdout = iter([])
            returncode = 1

            def __init__(self, cmd, **kw):
                captured["cmd"], captured["cwd"] = cmd, kw.get("cwd")

            def wait(self):
                return 1

            def poll(self):
                return 1

        with tempfile.TemporaryDirectory() as tmp:
            fake_remotion = Path(tmp) / "remotion"
            (fake_remotion / "node_modules").mkdir(parents=True)
            job = MagicMock(id=999)
            with patch.object(render_mod, "REMOTION_DIR", fake_remotion), patch.object(render_mod.shutil, "which", return_value="npx"),                     patch.object(render_mod.subprocess, "Popen", FakeProc), patch.object(render_mod, "_update"):
                with self.assertRaises(ValidationError):
                    render_mod._remotion_render(MagicMock(), job, MagicMock(), Path("rel/props.json"), Path("rel/public"), Path("rel/out.mp4"), 10, 0.5)
        flags = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in captured["cmd"] if a.startswith(("--props=", "--public-dir="))}
        self.assertTrue(Path(flags["--props"]).is_absolute() and Path(flags["--public-dir"]).is_absolute(), flags)
        self.assertTrue(Path(captured["cmd"][5]).is_absolute())  # the output file


def tone(path: Path, seconds: float, freq=440, volume=0.5, silence_after: float = 0.0):
    """A sine WAV; `silence_after` pads silence at the end (so 'voice only in the first N seconds' is possible)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-af", f"volume={volume}"]
    if silence_after:
        cmd += ["-af", f"volume={volume},apad=pad_dur={silence_after}"]
    subprocess.run(cmd + ["-ar", "48000", "-ac", "1", str(path)], check=True)


def mean_volume(path: Path, start: float, length: float) -> float:
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(start), "-t", str(length), "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re as _re

    m = _re.search(r"mean_volume: (-?[\d.]+|-inf) dB", r.stderr)
    return float("-inf") if not m or m.group(1) == "-inf" else float(m.group(1))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class MusicMixTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.video = self.dir / "v.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=white:s=320x180:r=30:d=6", "-pix_fmt", "yuv420p", str(self.video)], check=True)
        self.voice = self.dir / "voice.wav"
        tone(self.voice, 2.0, volume=0.6, silence_after=4.0)  # speech-like energy only in the first 2 s
        self.music = self.dir / "music.wav"
        tone(self.music, 1.5, freq=220, volume=0.8)  # shorter than the video: must loop

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except PermissionError:
            pass

    def mix(self, music=None, db=-24.0):
        out = self.dir / ("with.mp4" if music else "without.mp4")
        cmd = render_mod.mux_command(self.video, self.voice, out, 6.0, False, str(music) if music else None, db)
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        return out

    def test_command_shape(self):
        plain = render_mod.mux_command(self.video, self.voice, self.dir / "o.mp4", 6.0, True)
        self.assertNotIn("-filter_complex", plain)
        with_music = render_mod.mux_command(self.video, self.voice, self.dir / "o.mp4", 6.0, True, str(self.music), -20.0)
        self.assertIn("-stream_loop", with_music)
        graph = with_music[with_music.index("-filter_complex") + 1]
        self.assertIn("sidechaincompress", graph)
        self.assertIn("volume=-20.0dB", graph)

    def test_music_loops_under_silence_and_fades_out(self):
        out = self.mix(self.music, db=-12.0)
        info = media.probe_duration(out)
        self.assertAlmostEqual(info, 6.0, delta=0.15)
        self.assertTrue(media.has_audio_stream(out))
        # after the voice ends (2 s) and after the 1.5 s file is exhausted, the looped music is still audible...
        mid = mean_volume(out, 3.0, 0.4)
        self.assertGreater(mid, -45.0)
        # ...and the fade-out (last 3 s) makes the very end quieter than the middle
        end = mean_volume(out, 5.6, 0.3)
        self.assertLess(end, mid - 3.0)
        # without music the same stretch is silent
        self.assertLess(mean_volume(self.mix(None), 3.0, 0.4), -60.0)

    def test_voice_stays_on_top_while_music_plays(self):
        voice_only = mean_volume(self.mix(None), 0.2, 1.5)
        mixed = mean_volume(self.mix(self.music, db=-12.0), 0.2, 1.5)
        # the ducked bed may add a little energy, but never more than ~3 dB above the voice alone
        self.assertLess(mixed - voice_only, 3.0)

    def test_music_file_is_validated(self):
        check = RenderService._check_music
        check(RenderParams(music_path=str(self.music)))  # fine
        with self.assertRaises(ValidationError):
            check(RenderParams(music_path="relative/music.mp3"))
        with self.assertRaises(ValidationError):
            check(RenderParams(music_path=str(self.dir / "missing.mp3")))
        bad_ext = self.dir / "song.txt"
        bad_ext.write_text("x")
        with self.assertRaises(ValidationError):
            check(RenderParams(music_path=str(bad_ext)))
        fake = self.dir / "fake.mp3"
        fake.write_text("not audio at all")
        with self.assertRaises(ValidationError):
            check(RenderParams(music_path=str(fake)))
        with self.assertRaises(ValidationError):
            check(RenderParams(music_path=str(self.music), music_db=0.0))


def make_video(path: Path, *, w=960, h=540, seconds=2.0, audio=True, black=None):
    """Tiny test clip with ffmpeg. `black=(start, end)` blanks that interval."""
    vf = f"color=c=white:s={w}x{h}:r=30:d={seconds}"
    if black:
        vf += f",drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,{black[0]},{black[1]})'"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", vf]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=300:d={seconds}"]
    cmd += ["-pix_fmt", "yuv420p", "-shortest", str(path)]
    subprocess.run(cmd, check=True)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class QualityCheckTests(ManifestCase):
    def check(self, path, expect=(960, 540), seconds=2.0):
        master = self.root / "none.wav"
        return quality_check(self.db, self.p.id, path, {"w": expect[0], "h": expect[1]}, seconds, False, master)

    def test_good_clip_passes(self):
        self.timeline_ready()
        f = Path(self.tmp.name) / "ok.mp4"
        make_video(f)
        r = self.check(f)
        self.assertTrue(r["ok"], r["issues"])
        self.assertTrue(r["has_audio"])

    def test_wrong_size_no_audio_and_wrong_length_are_all_reported(self):
        self.timeline_ready()
        f = Path(self.tmp.name) / "bad.mp4"
        make_video(f, w=640, h=360, seconds=1.0, audio=False)
        codes = {i["code"] for i in self.check(f, seconds=2.0)["issues"]}
        self.assertTrue({"bad_resolution", "no_audio", "bad_duration"} <= codes)

    def test_black_frames_name_the_scene(self):
        self.timeline_ready()
        timings = self.db.query(DocumentarySceneTiming).filter_by(project_id=self.p.id).order_by(DocumentarySceneTiming.order_index).all()
        # squeeze the first two scenes' timeline into the clip so a known scene is blacked out
        timings[0].start, timings[0].end = 0.0, 1.0
        timings[1].start, timings[1].end = 1.0, 2.0
        self.db.commit()
        f = Path(self.tmp.name) / "black.mp4"
        make_video(f, black=(1.2, 1.8))
        issues = [i for i in self.check(f)["issues"] if i["code"] == "black_frames"]
        self.assertTrue(issues)
        self.assertEqual(issues[0]["scene"], timings[1].scene_key)
        self.assertIn(timings[1].scene_key, issues[0]["message"])


@unittest.skipUnless(HAVE_TOOLCHAIN, "needs node + npx + ffmpeg + remotion/node_modules")
class RealRenderTests(ManifestCase):
    def test_tiny_preview_renders_validates_and_has_sound(self):
        self.timeline_ready()
        factory = sessionmaker(bind=self.engine)
        render = RenderService(self.db, self.root, session_factory=factory)
        job, reused = render.start(self.p.id, RenderParams(kind="preview", scale=0.25, seconds=1.5, burn_subtitles=True))
        self.assertFalse(reused)
        th = render_mod._THREADS[job.id]
        th.join(timeout=420)
        self.assertFalse(th.is_alive(), "render did not finish in time")
        self.db.expire_all()
        job = self.db.get(DocumentaryRenderJob, job.id)
        self.assertEqual(job.status, "succeeded", job.error)
        self.assertEqual(job.progress, 1.0)
        out = Path(job.output_path)
        self.assertTrue(out.is_file())
        self.assertTrue(job.qc["ok"], job.qc["issues"])
        self.assertTrue(job.qc["has_audio"])
        self.assertEqual(job.qc["audio_sample_rate"], 48000)  # regression: loudnorm used to leave it at 96 kHz
        self.assertEqual([w for w in job.qc["warnings"] if w["code"] == "audio_sample_rate"], [])
        self.assertEqual((job.qc["width"], job.qc["height"]), (480, 270))
        self.assertAlmostEqual(job.duration_sec, 1.5, delta=0.15)
        self.assertIn("job", render.log_tail(job).lower())
        # the identical request is now a cache hit
        again, reused2 = render.start(self.p.id, RenderParams(kind="preview", scale=0.25, seconds=1.5, burn_subtitles=True))
        self.assertEqual((again.id, reused2), (job.id, True))


if __name__ == "__main__":
    unittest.main()
