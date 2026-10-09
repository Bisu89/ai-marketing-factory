"""Audio-first timeline: align each narration segment to word timestamps,
then assemble scene timings and subtitles against the master audio.

Per-segment alignments are cached by the segment's audio cache_key (the slow
part, Whisper, runs once per audio version). Assembly is a cheap, pure
recomputation from cached alignments + the current master offsets, so a
changed segment only re-aligns itself and every other segment just shifts.

Timing provenance is always recorded and shown: tts_provider (the engine's
own word stamps), whisper_local, estimated (a guess, always flagged), or
manual. Estimated timing is never presented as accurate.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary import align_whisper
from app.modules.documentary.alignment import (
    AlignedWord,
    align_words,
    coverage,
    estimated_words,
    split_subtitle_chunks,
)
from app.modules.documentary.models import (
    DocumentaryNarrationSegment,
    DocumentarySceneTiming,
    DocumentaryScene,
    DocumentarySegmentAlignment,
    DocumentarySubtitle,
    DocumentaryTimingOverride,
    DocumentaryUsage,
)
from app.modules.documentary.narration import NarrationService
from app.modules.documentary.schemas import ReviewIssue, ReviewOut
from app.modules.documentary.tts import WordStamp

GOOD_COVERAGE = 0.85  # TTS/Whisper stamps are trusted as the segment's timing at/above this
REVIEW_COVERAGE = 0.70  # a scene below this share of really-matched words needs a human look
MIN_SCENE_SEC = 0.2
MIN_SUBTITLE_SEC = 0.3
SUBTITLE_TAIL_SEC = 0.15
CONTIGUITY_TOL = 0.011
BOUNDARY_TOL = 0.05
SUBTITLE_TEXT_COVERAGE = 0.98

Transcriber = Callable[..., list[WordStamp]]


def _fmt_srt(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class TimelineService:
    def __init__(self, db: Session, root: Path, transcriber: Transcriber | None = None):
        self.db = db
        self.root = root
        self.narration = NarrationService(db, root)
        self._transcribe = transcriber or align_whisper.transcribe_words

    # -- alignment (per segment, cached) ----------------------------------------
    def alignment_for(self, project_id: int, segment_key: str) -> DocumentarySegmentAlignment | None:
        return self.db.scalars(
            select(DocumentarySegmentAlignment).where(
                DocumentarySegmentAlignment.project_id == project_id,
                DocumentarySegmentAlignment.segment_key == segment_key,
            )
        ).first()

    def _align_one(self, project_id: int, seg: DocumentaryNarrationSegment, method: str) -> tuple[str, list[AlignedWord]]:
        script = seg.text.split()
        total = float(seg.duration_sec or 0.0)
        stamps = [WordStamp(w["text"], w["start"], w["end"]) for w in (seg.word_stamps or [])]

        def from_stamps(source: str, st: list[WordStamp]) -> tuple[str, list[AlignedWord]]:
            return source, align_words(script, st, total)

        if method == "estimated":
            return "estimated", estimated_words(script, total)
        if method == "tts" and not stamps:
            raise ValidationError(f"Đoạn {seg.segment_key}: backend giọng đọc không trả timestamp từng từ.")
        if method in ("auto", "tts") and stamps:
            source, words = from_stamps("tts_provider", stamps)
            if method == "tts" or coverage(words) >= GOOD_COVERAGE:
                return source, words
        if method in ("auto", "whisper"):
            if align_whisper.is_available():
                got = self._transcribe(Path(seg.audio_path), language="vi", prompt=seg.text)
                self.db.add(DocumentaryUsage(project_id=project_id, kind="alignment", provider="whisper_local",
                                             model="faster-whisper", ref=seg.segment_key, cost_usd=0.0))
                source, words = from_stamps("whisper_local", got)
                if method == "whisper" or coverage(words) >= GOOD_COVERAGE or not stamps:
                    return source, words
            elif method == "whisper":
                raise ValidationError("Chưa cài faster-whisper: chạy `pip install faster-whisper`.")
        if stamps:  # weak provider stamps are still better than a blind guess, but flagged by coverage
            return from_stamps("tts_provider", stamps)
        return "estimated", estimated_words(script, total)

    def align(self, project_id: int, method: str = "auto", only: list[str] | None = None) -> dict:
        if method not in ("auto", "tts", "whisper", "estimated"):
            raise ValidationError(f"Phương pháp căn chỉnh không hợp lệ: {method!r}")
        segments = self.narration.list(project_id)
        stale = [s.segment_key for s in segments if not self.narration.is_current(s)]
        if not segments or stale:
            raise ValidationError(f"Cần audio hiện hành cho mọi đoạn trước khi căn chỉnh — còn thiếu/cũ: {stale or 'chưa có đoạn nào'}.")
        aligned, cached, report = [], 0, []
        for seg in segments:
            if only is not None and seg.segment_key not in only:
                continue
            existing = self.alignment_for(project_id, seg.segment_key)
            if existing is not None and existing.cache_key == seg.cache_key and method == "auto":
                cached += 1
                continue
            source, words = self._align_one(project_id, seg, method)
            row = existing or DocumentarySegmentAlignment(project_id=project_id, segment_key=seg.segment_key)
            row.cache_key, row.source, row.coverage = seg.cache_key, source, round(coverage(words), 4)
            row.words = [[w.text, w.start, w.end, w.matched] for w in words]
            self.db.add(row)
            self.db.commit()
            aligned.append(seg.segment_key)
            report.append({"segment": seg.segment_key, "source": source, "coverage": row.coverage})
        return {"aligned": aligned, "cached": cached, "details": report}

    # -- assembly -------------------------------------------------------------------
    def assemble(self, project_id: int) -> dict:
        segments = self.narration.list(project_id)
        stale = [s.segment_key for s in segments if not self.narration.is_current(s)]
        if not segments or stale:
            raise ValidationError(f"Audio chưa hiện hành cho đoạn: {stale or 'chưa có đoạn nào'}.")
        if self.narration.review(project_id):
            raise ValidationError("Cần ghép narration master mới nhất trước khi dựng timeline.")
        digest = self.narration.master_digest(segments)
        scenes = {
            s.scene_key: s
            for s in self.db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == project_id))
        }
        overrides = {
            o.scene_key: o
            for o in self.db.scalars(select(DocumentaryTimingOverride).where(DocumentaryTimingOverride.project_id == project_id))
        }
        master_total = segments[-1].master_end
        rows: list[dict] = []
        for seg in segments:
            al = self.alignment_for(project_id, seg.segment_key)
            if al is None or al.cache_key != seg.cache_key:
                raise ValidationError(f"Đoạn {seg.segment_key} chưa được căn chỉnh cho audio hiện tại — chạy bước căn chỉnh.")
            in_seg = [scenes.get(k) for k in seg.scene_keys]
            if any(s is None for s in in_seg) or " ".join(s.narration_text for s in in_seg) != seg.text:
                raise ValidationError(f"Lời dẫn của các cảnh trong đoạn {seg.segment_key} đã đổi — hãy chia đoạn narration lại.")
            words = [AlignedWord(t, s, e, m) for t, s, e, m in al.words]
            ptr, locals_ = 0, []
            for s in in_seg:
                n = len(s.narration_text.split())
                locals_.append((s, words[ptr : ptr + n]))
                ptr += n
            starts = [0.0 if i == 0 else sw[0].start for i, (_, sw) in enumerate(locals_)]
            for i, (s, _) in enumerate(locals_):
                o = overrides.get(s.scene_key)
                if i > 0 and o is not None and o.segment_cache_key == seg.cache_key:
                    starts[i] = o.local_start
            for i in range(1, len(starts)):  # monotonic, with a minimum scene length
                starts[i] = max(starts[i], starts[i - 1] + MIN_SCENE_SEC)
            for i, (s, sw) in enumerate(locals_):
                o = overrides.get(s.scene_key)
                manual = i > 0 and o is not None and o.segment_cache_key == seg.cache_key
                cov = sum(1 for w in sw if w.matched) / len(sw) if sw else 0.0
                rows.append(
                    {
                        "scene": s, "start": seg.master_start + starts[i], "source": "manual" if manual else al.source,
                        "coverage": round(cov, 4), "manual": manual,
                        "words": [[w.text, round(seg.master_start + w.start, 3), round(seg.master_start + w.end, 3), w.matched] for w in sw],
                    }
                )
        for i, r in enumerate(rows):  # continuous: a scene runs until the next one begins
            r["end"] = rows[i + 1]["start"] if i + 1 < len(rows) else master_total

        self.db.execute(delete(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id))
        self.db.execute(delete(DocumentarySubtitle).where(DocumentarySubtitle.project_id == project_id))
        subs: list[dict] = []
        for r in rows:
            s = r["scene"]
            needs = (not r["manual"]) and (r["source"] == "estimated" or r["coverage"] < REVIEW_COVERAGE)
            self.db.add(
                DocumentarySceneTiming(
                    project_id=project_id, scene_key=s.scene_key, order_index=s.order_index, start=round(r["start"], 3),
                    end=round(r["end"], 3), source=r["source"], coverage=r["coverage"], needs_review=needs,
                    master_hash=digest, words=r["words"],
                )
            )
            s.actual_duration = round(r["end"] - r["start"], 3)
            words = [AlignedWord(t, a, b, m) for t, a, b, m in r["words"]]
            for chunk in split_subtitle_chunks(words):
                subs.append({"scene_key": s.scene_key, "source": r["source"], "start": chunk[0].start, "end": chunk[-1].end,
                             "text": " ".join(w.text for w in chunk), "scene_end": r["end"]})
        for i, sub in enumerate(subs):
            nxt = subs[i + 1]["start"] if i + 1 < len(subs) else master_total
            end = max(sub["end"] + SUBTITLE_TAIL_SEC, sub["start"] + MIN_SUBTITLE_SEC)
            end = min(end, nxt, master_total)
            if end <= sub["start"]:
                end = min(sub["start"] + 0.05, master_total)
            self.db.add(
                DocumentarySubtitle(project_id=project_id, order_index=i + 1, start=round(sub["start"], 3), end=round(end, 3),
                                    text=sub["text"], scene_key=sub["scene_key"], source=sub["source"])
            )
        self.db.commit()
        review = self.review(project_id)
        return {"scenes": len(rows), "subtitles": len(subs), "errors": len(review.issues), "warnings": len(review.warnings)}

    # -- manual correction --------------------------------------------------------------
    def set_scene_start(self, project_id: int, scene_key: str, start: float) -> dict:
        segs = self.narration.list(project_id)
        seg = next((s for s in segs if scene_key in s.scene_keys), None)
        if seg is None:
            raise NotFoundError("scene in narration", scene_key)
        idx = seg.scene_keys.index(scene_key)
        if idx == 0:
            raise ValidationError("Cảnh đầu của một đoạn bắt đầu cùng audio của đoạn; chỉnh ranh giới ở cảnh sau nó.")
        timings = {t.scene_key: t for t in self.db.scalars(select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id))}
        prev, nxt = timings.get(seg.scene_keys[idx - 1]), None
        if idx + 1 < len(seg.scene_keys):
            nxt = timings.get(seg.scene_keys[idx + 1])
        if prev is None:
            raise ValidationError("Chưa dựng timeline — hãy căn chỉnh và dựng trước khi chỉnh tay.")
        upper = nxt.start if nxt is not None else seg.master_end
        if not (prev.start + MIN_SCENE_SEC <= start <= upper - MIN_SCENE_SEC):
            raise ValidationError(
                f"Thời điểm bắt đầu phải nằm giữa {prev.start + MIN_SCENE_SEC:.2f}s và {upper - MIN_SCENE_SEC:.2f}s "
                "(giữ cảnh trước/sau tối thiểu 0.2s)."
            )
        self.db.execute(
            delete(DocumentaryTimingOverride).where(
                DocumentaryTimingOverride.project_id == project_id, DocumentaryTimingOverride.scene_key == scene_key
            )
        )
        self.db.add(DocumentaryTimingOverride(project_id=project_id, scene_key=scene_key, segment_cache_key=seg.cache_key,
                                              local_start=round(start - seg.master_start, 3)))
        self.db.commit()
        return self.assemble(project_id)

    def clear_override(self, project_id: int, scene_key: str) -> dict:
        self.db.execute(
            delete(DocumentaryTimingOverride).where(
                DocumentaryTimingOverride.project_id == project_id, DocumentaryTimingOverride.scene_key == scene_key
            )
        )
        self.db.commit()
        return self.assemble(project_id)

    # -- reading ------------------------------------------------------------------------------
    def timings(self, project_id: int) -> list[DocumentarySceneTiming]:
        return list(
            self.db.scalars(
                select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id).order_by(DocumentarySceneTiming.order_index)
            )
        )

    def subtitles(self, project_id: int) -> list[DocumentarySubtitle]:
        return list(
            self.db.scalars(
                select(DocumentarySubtitle).where(DocumentarySubtitle.project_id == project_id).order_by(DocumentarySubtitle.order_index)
            )
        )

    def srt(self, project_id: int) -> str:
        return "".join(
            f"{s.order_index}\n{_fmt_srt(s.start)} --> {_fmt_srt(s.end)}\n{s.text}\n\n" for s in self.subtitles(project_id)
        )

    # -- validation / gate 4 ----------------------------------------------------------------------
    def review(self, project_id: int) -> ReviewOut:
        base = self.narration.review(project_id)
        if base:
            return ReviewOut(ok=False, issues=base)
        segments = self.narration.list(project_id)
        digest = self.narration.master_digest(segments)
        timings = self.timings(project_id)
        issues: list[ReviewIssue] = []
        warnings: list[ReviewIssue] = []
        if not timings:
            return ReviewOut(ok=False, issues=[ReviewIssue(code="no_timeline", message="Chưa căn chỉnh/dựng timeline cho narration.")])
        scene_keys = [k for s in segments for k in s.scene_keys]
        by_key = {t.scene_key: t for t in timings}
        for k in scene_keys:
            if k not in by_key:
                issues.append(ReviewIssue(code="scene_no_timing", message=f"Cảnh {k}: chưa có timing."))
        total = segments[-1].master_end or 0.0
        prev = None
        for k in scene_keys:
            t = by_key.get(k)
            if t is None:
                continue
            if t.master_hash != digest:
                issues.append(ReviewIssue(code="timing_stale", message=f"Cảnh {k}: timing cũ so với audio hiện tại — dựng lại timeline."))
            if t.end - t.start <= 0:
                issues.append(ReviewIssue(code="bad_duration", message=f"Cảnh {k}: thời lượng không dương ({t.start:.2f}→{t.end:.2f})."))
            if t.start < -BOUNDARY_TOL or t.end > total + BOUNDARY_TOL:
                issues.append(ReviewIssue(code="out_of_audio", message=f"Cảnh {k}: nằm ngoài độ dài audio ({total:.2f}s)."))
            if prev is not None and abs(t.start - prev.end) > CONTIGUITY_TOL:
                kind = "chồng lấn" if t.start < prev.end else "hở"
                issues.append(ReviewIssue(code="scene_gap_overlap", message=f"Cảnh {prev.scene_key}→{k}: {kind} {abs(t.start - prev.end):.2f}s."))
            if t.needs_review:
                why = "timing ước lượng (không có timestamp thật)" if t.source == "estimated" else f"chỉ khớp {t.coverage:.0%} số từ"
                warnings.append(ReviewIssue(code="needs_timing_review", message=f"Cảnh {k}: {why} — nên nghe và chỉnh tay."))
            prev = t
        if timings and abs(timings[0].start) > CONTIGUITY_TOL:
            issues.append(ReviewIssue(code="timeline_start", message=f"Timeline không bắt đầu tại 0s ({timings[0].start:.2f}s)."))
        if timings and abs(timings[-1].end - total) > BOUNDARY_TOL:
            issues.append(ReviewIssue(code="timeline_end", message=f"Timeline kết thúc {timings[-1].end:.2f}s, audio dài {total:.2f}s."))
        issues += self._subtitle_issues(project_id, by_key, total)
        return ReviewOut(ok=not issues, issues=issues, warnings=warnings)

    def _subtitle_issues(self, project_id: int, by_key: dict, total: float) -> list[ReviewIssue]:
        subs = self.subtitles(project_id)
        issues: list[ReviewIssue] = []
        prev_end = -1.0
        for s in subs:
            if s.end <= s.start:
                issues.append(ReviewIssue(code="subtitle_duration", message=f"Phụ đề #{s.order_index}: thời lượng không dương."))
            if s.start < prev_end - CONTIGUITY_TOL:
                issues.append(ReviewIssue(code="subtitle_order", message=f"Phụ đề #{s.order_index}: chồng lấn phụ đề trước."))
            if s.start < -BOUNDARY_TOL or s.end > total + BOUNDARY_TOL:
                issues.append(ReviewIssue(code="subtitle_out_of_audio", message=f"Phụ đề #{s.order_index}: nằm ngoài audio."))
            prev_end = s.end
        scenes = {
            s.scene_key: s
            for s in self.db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == project_id))
        }
        sub_words: dict[str, int] = {}
        for s in subs:
            sub_words[s.scene_key] = sub_words.get(s.scene_key, 0) + len(s.text.split())
        for k, sc in scenes.items():
            if k in by_key:
                want = len(sc.narration_text.split())
                if want and sub_words.get(k, 0) / want < SUBTITLE_TEXT_COVERAGE:
                    issues.append(ReviewIssue(code="subtitle_coverage", message=f"Cảnh {k}: phụ đề chỉ phủ {sub_words.get(k, 0)}/{want} từ."))
        return issues
