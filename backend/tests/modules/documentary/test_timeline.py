"""Documentary alignment, timeline and subtitles (feature 167). Whisper is
replaced by a fake transcriber -- these tests never load a model."""

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.exceptions import ValidationError
from app.modules.documentary import align_whisper, media
from app.modules.documentary.alignment import (
    AlignedWord,
    align_words,
    coverage,
    estimated_words,
    fold,
    split_subtitle_chunks,
)
from app.modules.documentary.models import DocumentaryScene, DocumentarySceneTiming, DocumentarySubtitle
from app.modules.documentary.timeline import TimelineService, _fmt_srt
from app.modules.documentary.tts import WordStamp
from tests.modules.documentary.test_narration import NarrationCase


def even_stamps(words, total, scale=0.9):
    step = total / len(words)
    return [WordStamp(w, i * step, i * step + step * scale) for i, w in enumerate(words)]


class FoldTests(unittest.TestCase):
    def test_fold_ignores_case_punctuation_and_diacritics(self):
        self.assertEqual(fold("Constantinople,"), fold("constantinople"))
        self.assertEqual(fold("Thất"), fold("that"))
        self.assertEqual(fold("Đã"), fold("da"))
        self.assertNotEqual(fold("năm"), fold("nấm") + "x")


class AlignWordsTests(unittest.TestCase):
    def test_exact_match_uses_real_stamps(self):
        script = "Xin chào các bạn.".split()
        words = align_words(script, even_stamps(script, 4.0), 4.0)
        self.assertTrue(all(w.matched for w in words))
        self.assertEqual(coverage(words), 1.0)
        self.assertEqual(words[2].start, 2.0)

    def test_recogniser_errors_do_not_break_alignment(self):
        script = "thành Constantinople thất thủ năm 1453".split()
        heard = [WordStamp("thành", 0, 0.4), WordStamp("constantinople", 0.5, 1.4), WordStamp("thất", 1.5, 1.8),
                 WordStamp("thủ", 1.9, 2.2), WordStamp("năm", 2.3, 2.6), WordStamp("một", 2.7, 3.0)]  # '1453' misheard
        words = align_words(script, heard, 4.0)
        self.assertEqual([w.matched for w in words], [True, True, True, True, True, False])
        self.assertGreaterEqual(words[5].start, words[4].end - 1e-6)  # interpolated after its neighbour

    def test_dropped_word_is_interpolated_and_flagged(self):
        script = "a b c d e".split()
        heard = [s for i, s in enumerate(even_stamps(script, 5.0)) if i != 2]
        words = align_words(script, heard, 5.0)
        self.assertFalse(words[2].matched)
        self.assertTrue(words[1].end <= words[2].start + 1e-6 and words[2].end <= words[3].start + 1e-6)
        self.assertAlmostEqual(coverage(words), 0.8)

    def test_extra_heard_words_are_ignored(self):
        script = "một hai ba".split()
        heard = even_stamps("một ờ hai ừm ba".split(), 5.0)
        words = align_words(script, heard, 5.0)
        self.assertTrue(all(w.matched for w in words))

    def test_no_stamps_is_all_unmatched_and_within_audio(self):
        words = align_words("a b c".split(), [], 3.0)
        self.assertFalse(any(w.matched for w in words))
        self.assertEqual((words[0].start, words[-1].end), (0.0, 3.0))

    def test_monotonic_and_clipped(self):
        script = "a b c".split()
        heard = [WordStamp("a", 0, 9), WordStamp("b", 1, 2), WordStamp("c", 2, 9)]  # nonsense overlaps
        words = align_words(script, heard, 3.0)
        starts = [w.start for w in words]
        self.assertEqual(starts, sorted(starts))
        self.assertTrue(all(0 <= w.start <= w.end <= 3.0 for w in words))

    def test_estimated_is_flagged_and_spans_audio(self):
        words = estimated_words("Một câu ngắn. Câu thứ hai dài hơn nhiều.".split(), 6.0)
        self.assertFalse(any(w.matched for w in words))
        self.assertAlmostEqual(words[-1].end, 6.0, places=2)
        self.assertEqual([w.start for w in words], sorted(w.start for w in words))


class SubtitleChunkTests(unittest.TestCase):
    def words(self, text):
        return [AlignedWord(w, i, i + 0.5, True) for i, w in enumerate(text.split())]

    def test_breaks_at_sentence_ends(self):
        chunks = split_subtitle_chunks(self.words("Câu một. Câu hai! Câu ba?"))
        self.assertEqual([" ".join(w.text for w in c) for c in chunks], ["Câu một.", "Câu hai!", "Câu ba?"])

    def test_long_sentence_splits_at_comma(self):
        text = "Đây là phần đầu của một câu rất dài, và đây là phần sau của chính câu đó với nhiều chữ nữa để vượt giới hạn."
        chunks = split_subtitle_chunks(self.words(text), max_chars=60)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0][-1].text.endswith(","))
        self.assertEqual(" ".join(w.text for c in chunks for w in c), text)  # nothing lost or reordered

    def test_srt_time_format(self):
        self.assertEqual(_fmt_srt(3661.5), "01:01:01,500")
        self.assertEqual(_fmt_srt(0.0), "00:00:00,000")


class TimelineCase(NarrationCase):
    def setUp(self):
        super().setUp()
        self.calls = []

    def transcriber(self, drop=()):
        def t(audio_path, language="vi", prompt=None):
            self.calls.append(Path(audio_path).name)
            words = prompt.split()
            stamps = even_stamps(words, media.probe_duration(Path(audio_path)))
            return [s for i, s in enumerate(stamps) if i not in drop]

        return t

    def tl(self, **kw):
        return TimelineService(self.db, self.root, transcriber=self.transcriber(**kw))

    def prepared(self, **kw):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        return self.tl(**kw)


class AlignAndAssembleTests(TimelineCase):
    def test_align_requires_current_audio(self):
        self.to_audio_ready()
        self.svc.plan_narration(self.p.id)
        with self.assertRaises(ValidationError):
            self.tl().align(self.p.id)

    def test_whisper_path_assembles_a_contiguous_timeline(self):
        tl = self.prepared()
        res = tl.align(self.p.id, "whisper")
        segs = self.narr.list(self.p.id)
        self.assertEqual(len(res["aligned"]), len(segs))
        self.assertTrue(all(d["source"] == "whisper_local" and d["coverage"] == 1.0 for d in res["details"]))
        tl.assemble(self.p.id)
        timings = tl.timings(self.p.id)
        scenes = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id).count()
        self.assertEqual(len(timings), scenes)
        self.assertEqual(timings[0].start, 0.0)
        for a, b in zip(timings, timings[1:]):
            self.assertAlmostEqual(a.end, b.start, places=3)  # no gaps, no overlaps
        self.assertAlmostEqual(timings[-1].end, segs[-1].master_end, places=2)
        self.assertTrue(all(t.end > t.start for t in timings))
        self.assertTrue(all(not t.needs_review for t in timings))
        review = tl.review(self.p.id)
        self.assertTrue(review.ok, review.issues)
        # scene durations now come from real audio, not the text-length guess
        sc = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id).all()
        self.assertTrue(all(s.actual_duration and s.actual_duration > 0 for s in sc))

    def test_subtitles_are_ordered_in_bounds_and_cover_the_text(self):
        tl = self.prepared()
        tl.align(self.p.id, "whisper")
        tl.assemble(self.p.id)
        subs = tl.subtitles(self.p.id)
        total = self.narr.list(self.p.id)[-1].master_end
        self.assertTrue(subs)
        for a, b in zip(subs, subs[1:]):
            self.assertLessEqual(a.end, b.start + 0.011)
        self.assertTrue(all(0 <= s.start < s.end <= total + 0.05 for s in subs))
        script_words = sum(len(s.narration_text.split()) for s in self.db.query(DocumentaryScene).filter_by(project_id=self.p.id))
        self.assertEqual(sum(len(s.text.split()) for s in subs), script_words)
        srt = tl.srt(self.p.id)
        self.assertRegex(srt, r"^1\n\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}\n")
        self.assertEqual(len(re.findall(r"-->", srt)), len(subs))

    def test_tts_stamps_are_used_without_calling_whisper(self):
        tl = self.prepared()
        for seg in self.narr.list(self.p.id):
            seg.word_stamps = [{"text": s.text, "start": s.start, "end": s.end}
                               for s in even_stamps(seg.text.split(), seg.duration_sec)]
        self.db.commit()
        res = tl.align(self.p.id, "auto")
        self.assertEqual({d["source"] for d in res["details"]}, {"tts_provider"})
        self.assertEqual(self.calls, [])

    def test_poor_tts_stamps_fall_back_to_whisper(self):
        tl = self.prepared()
        for seg in self.narr.list(self.p.id):
            seg.word_stamps = [{"text": "zzz", "start": 0.0, "end": 0.1}]  # nothing matches the script
        self.db.commit()
        res = tl.align(self.p.id, "auto")
        self.assertEqual({d["source"] for d in res["details"]}, {"whisper_local"})
        self.assertTrue(self.calls)

    def test_no_whisper_and_no_stamps_gives_flagged_estimate(self):
        tl = self.prepared()
        with patch.object(align_whisper, "is_available", return_value=False):
            res = tl.align(self.p.id, "auto")
        self.assertEqual({d["source"] for d in res["details"]}, {"estimated"})
        tl.assemble(self.p.id)
        timings = tl.timings(self.p.id)
        self.assertTrue(all(t.needs_review and t.source == "estimated" for t in timings))
        review = tl.review(self.p.id)
        self.assertTrue(review.ok)  # structurally valid...
        self.assertEqual(len(review.warnings), len(timings))  # ...but every scene is called out as a guess
        self.assertIn("ước lượng", review.warnings[0].message)

    def test_forcing_whisper_when_missing_is_a_clear_error(self):
        tl = self.prepared()
        with patch.object(align_whisper, "is_available", return_value=False):
            with self.assertRaises(ValidationError):
                tl.align(self.p.id, "whisper")

    def test_weakly_matched_scene_is_flagged_for_review(self):
        tl = self.prepared(drop=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10))  # whisper "missed" many words
        tl.align(self.p.id, "whisper")
        tl.assemble(self.p.id)
        review = tl.review(self.p.id)
        self.assertTrue(any(t.needs_review for t in tl.timings(self.p.id)))
        self.assertTrue(any(w.code == "needs_timing_review" for w in review.warnings))

    def test_alignment_is_cached_and_only_changed_segment_is_redone(self):
        tl = self.prepared()
        tl.align(self.p.id, "whisper")
        n = len(self.calls)
        again = tl.align(self.p.id, "auto")
        self.assertEqual((again["aligned"], again["cached"]), ([], len(self.narr.list(self.p.id))))
        self.assertEqual(len(self.calls), n)  # no Whisper work repeated
        # edit one scene -> one new segment -> exactly one re-alignment
        scene = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        scene.narration_text += " Thêm một câu hoàn toàn mới."
        self.db.commit()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        redo = tl.align(self.p.id, "auto")
        self.assertEqual(len(redo["aligned"]), 1)
        self.assertEqual(redo["cached"], len(self.narr.list(self.p.id)) - 1)
        tl.assemble(self.p.id)
        self.assertTrue(tl.review(self.p.id).ok)

    def test_stale_timeline_after_audio_change_is_detected(self):
        tl = self.prepared()
        tl.align(self.p.id, "whisper")
        tl.assemble(self.p.id)
        scene = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, order_index=1).one()
        scene.narration_text += " Câu mới."
        self.db.commit()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        codes = {i.code for i in tl.review(self.p.id).issues}
        self.assertTrue(codes & {"timing_stale", "scene_no_timing"})
        with self.assertRaises(ValidationError):
            tl.assemble(self.p.id)  # needs re-alignment of the changed segment first

    def test_assemble_without_alignment_fails_clearly(self):
        tl = self.prepared()
        with self.assertRaises(ValidationError):
            tl.assemble(self.p.id)


class ManualCorrectionTests(TimelineCase):
    def built(self):
        tl = self.prepared()
        tl.align(self.p.id, "whisper")
        tl.assemble(self.p.id)
        return tl

    def mid_scene(self, tl):
        seg = next(s for s in self.narr.list(self.p.id) if len(s.scene_keys) >= 3)
        return seg, seg.scene_keys[1]

    def test_move_a_boundary_keeps_the_timeline_contiguous(self):
        tl = self.built()
        seg, key = self.mid_scene(tl)
        t = {x.scene_key: x for x in tl.timings(self.p.id)}
        new_start = t[key].start + 0.1
        tl.set_scene_start(self.p.id, key, new_start)
        t2 = {x.scene_key: x for x in tl.timings(self.p.id)}
        self.assertAlmostEqual(t2[key].start, new_start, places=2)
        self.assertEqual(t2[key].source, "manual")
        self.assertFalse(t2[key].needs_review)
        self.assertAlmostEqual(t2[seg.scene_keys[0]].end, new_start, places=2)
        self.assertTrue(tl.review(self.p.id).ok)

    def test_invalid_corrections_are_rejected(self):
        tl = self.built()
        seg, key = self.mid_scene(tl)
        with self.assertRaises(ValidationError):
            tl.set_scene_start(self.p.id, seg.scene_keys[0], 1.0)  # first scene of a segment is fixed by the audio
        t = {x.scene_key: x for x in tl.timings(self.p.id)}
        with self.assertRaises(ValidationError):
            tl.set_scene_start(self.p.id, key, t[seg.scene_keys[0]].start)  # would zero the previous scene
        with self.assertRaises(ValidationError):
            tl.set_scene_start(self.p.id, key, seg.master_end + 5)

    def test_override_survives_reassembly_and_can_be_cleared(self):
        tl = self.built()
        seg, key = self.mid_scene(tl)
        before = {x.scene_key: x.start for x in tl.timings(self.p.id)}[key]
        tl.set_scene_start(self.p.id, key, before + 0.15)
        tl.assemble(self.p.id)
        self.assertEqual({x.scene_key: x.source for x in tl.timings(self.p.id)}[key], "manual")
        tl.clear_override(self.p.id, key)
        after = {x.scene_key: x for x in tl.timings(self.p.id)}[key]
        self.assertAlmostEqual(after.start, before, places=2)
        self.assertEqual(after.source, "whisper_local")

    def test_override_is_dropped_when_its_segment_audio_changes(self):
        tl = self.built()
        seg, key = self.mid_scene(tl)
        start = {x.scene_key: x.start for x in tl.timings(self.p.id)}[key]
        tl.set_scene_start(self.p.id, key, start + 0.15)
        first = self.db.query(DocumentaryScene).filter_by(project_id=self.p.id, scene_key=seg.scene_keys[0]).one()
        first.narration_text += " Thêm câu."
        self.db.commit()
        self.svc.plan_narration(self.p.id)
        self.svc.generate_narration(self.p.id, "mock", None, False)
        self.narr.build_master(self.p.id)
        tl.align(self.p.id, "auto")
        tl.assemble(self.p.id)
        self.assertNotEqual({x.scene_key: x.source for x in tl.timings(self.p.id)}[key], "manual")


class ReviewDetectionTests(TimelineCase):
    def built(self):
        tl = self.prepared()
        tl.align(self.p.id, "whisper")
        tl.assemble(self.p.id)
        return tl

    def test_gap_between_scenes_is_reported_with_scene_ids(self):
        tl = self.built()
        t = tl.timings(self.p.id)
        t[1].start += 0.5
        self.db.commit()
        issues = tl.review(self.p.id).issues
        gaps = [i for i in issues if i.code == "scene_gap_overlap"]
        self.assertTrue(gaps)
        self.assertIn(t[0].scene_key, gaps[0].message)
        self.assertIn(t[1].scene_key, gaps[0].message)

    def test_scene_outside_audio_and_bad_duration(self):
        tl = self.built()
        t = tl.timings(self.p.id)
        t[-1].end += 10
        t[0].end = t[0].start - 1
        self.db.commit()
        codes = {i.code for i in tl.review(self.p.id).issues}
        self.assertTrue({"out_of_audio", "bad_duration"} <= codes)

    def test_bad_subtitles_are_reported(self):
        tl = self.built()
        subs = tl.subtitles(self.p.id)
        subs[0].end = subs[0].start  # zero length
        subs[1].start = subs[0].start - 0.2  # overlaps the previous one
        subs[-1].end += 99  # beyond the audio
        self.db.commit()
        codes = {i.code for i in tl.review(self.p.id).issues}
        self.assertTrue({"subtitle_duration", "subtitle_order", "subtitle_out_of_audio"} <= codes)

    def test_missing_subtitle_text_is_reported(self):
        tl = self.built()
        for s in tl.subtitles(self.p.id)[:3]:
            self.db.delete(s)
        self.db.commit()
        self.assertIn("subtitle_coverage", {i.code for i in tl.review(self.p.id).issues})

    def test_no_timeline_blocks_gate_four(self):
        self.prepared()
        with self.assertRaises(ValidationError) as cm:
            self.svc.approve(self.p.id, "narration_timing")
        self.assertIn("timeline", str(cm.exception))

    def test_gate_four_passes_with_estimated_timing_but_flags_it(self):
        tl = self.prepared()
        tl.align(self.p.id, "estimated")
        tl.assemble(self.p.id)
        self.assertTrue(tl.review(self.p.id).warnings)
        self.svc.approve(self.p.id, "narration_timing")  # a human may accept a flagged timeline; it is never hidden


if __name__ == "__main__":
    unittest.main()
