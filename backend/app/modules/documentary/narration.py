"""Narration segments: scenes -> paragraph-sized TTS units with stable IDs,
per-segment caching, retry limits, a spend ledger, and a rebuilt master.

Only a segment whose text (or voice settings) changed is synthesised again;
everything else is a cache hit. A paid backend never runs without an explicit
confirmation of the preflight estimate, and a known budget is enforced.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.modules.documentary import media
from app.modules.documentary.models import (
    DocumentaryNarrationSegment,
    DocumentaryProject,
    DocumentaryProjectCounter,
    DocumentaryScene,
    DocumentaryUsage,
)
from app.modules.documentary.schemas import ReviewIssue
from app.modules.documentary.tts import TTSBackend, get_backend


@dataclass(frozen=True)
class NarrationPolicy:
    min_chars: int = 350  # close a segment once it reaches this, at a scene boundary
    max_chars: int = 900  # never grow past this (one TTS request stays natural)
    stub_chars: int = 150  # a smaller remainder is merged into the previous segment
    gap_sec: float = 0.35  # silence between segments in the master
    max_attempts: int = 3  # per segment per text/voice version
    min_audio_sec: float = 0.2


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode("utf-8")).hexdigest()[:16]


def cache_key_for(seg_text_hash: str, backend: TTSBackend) -> str:
    return hashlib.sha256(f"{seg_text_hash}|{backend.fingerprint()}".encode("utf-8")).hexdigest()[:16]


def segment_scenes(scenes: list[DocumentaryScene], policy: NarrationPolicy) -> list[tuple[str, list[str]]]:
    """Pure: ordered scenes -> [(text, [scene_key, ...])]. Boundaries follow
    scene (sentence) edges and always close at a section change."""
    groups: list[list[DocumentaryScene]] = []
    cur: list[DocumentaryScene] = []
    chars = 0
    for s in scenes:
        n = len(s.narration_text)
        new_section = cur and cur[-1].section_kind != s.section_kind
        if cur and (new_section or chars >= policy.min_chars or chars + n > policy.max_chars):
            groups.append(cur)
            cur, chars = [], 0
        cur.append(s)
        chars += n + 1
    if cur:
        groups.append(cur)
    merged: list[list[DocumentaryScene]] = []
    for g in groups:
        size = sum(len(s.narration_text) for s in g)
        if merged and size < policy.stub_chars and merged[-1][-1].section_kind == g[0].section_kind:
            if sum(len(s.narration_text) for s in merged[-1]) + size <= policy.max_chars:
                merged[-1].extend(g)
                continue
        merged.append(g)
    return [(" ".join(s.narration_text for s in g), [s.scene_key for s in g]) for g in merged]


class NarrationService:
    def __init__(self, db: Session, root: Path, policy: NarrationPolicy | None = None):
        self.db = db
        self.root = root
        self.policy = policy or NarrationPolicy()

    def audio_dir(self, project_id: int) -> Path:
        return self.root / "_documentary" / f"project_{project_id}" / "narration"

    def master_path(self, project_id: int) -> Path:
        return self.audio_dir(project_id) / "narration_master.wav"

    def _meta_path(self, project_id: int) -> Path:
        return self.audio_dir(project_id) / "narration_master.json"

    # -- reading -----------------------------------------------------------
    def list(self, project_id: int) -> list[DocumentaryNarrationSegment]:
        return list(
            self.db.scalars(
                select(DocumentaryNarrationSegment)
                .where(DocumentaryNarrationSegment.project_id == project_id)
                .order_by(DocumentaryNarrationSegment.order_index)
            )
        )

    def get(self, project_id: int, key: str) -> DocumentaryNarrationSegment:
        s = self.db.scalars(
            select(DocumentaryNarrationSegment).where(
                DocumentaryNarrationSegment.project_id == project_id, DocumentaryNarrationSegment.segment_key == key
            )
        ).first()
        if s is None:
            raise NotFoundError("narration segment", key)
        return s

    def is_current(self, seg: DocumentaryNarrationSegment, backend: TTSBackend | None = None) -> bool:
        """Audio on disk matches the segment's current text AND the voice
        config of the backend that made it (so a later voice-setting change
        marks it stale instead of silently passing review)."""
        if backend is None:
            try:
                backend = get_backend(seg.provider) if seg.provider else None
            except ValidationError:
                backend = None
        if backend is None:
            return False
        return (
            seg.status == "ready"
            and seg.cache_key == cache_key_for(seg.text_hash, backend)
            and bool(seg.audio_path)
            and Path(seg.audio_path).is_file()
        )

    def spent_usd(self, project_id: int) -> tuple[float, int]:
        """-> (known spend, number of ledger rows whose cost is unknown)."""
        total = self.db.scalar(
            select(func.coalesce(func.sum(DocumentaryUsage.cost_usd), 0.0)).where(
                DocumentaryUsage.project_id == project_id, DocumentaryUsage.cost_usd.is_not(None)
            )
        )
        unknown = self.db.scalar(
            select(func.count()).where(DocumentaryUsage.project_id == project_id, DocumentaryUsage.cost_usd.is_(None))
        )
        return float(total or 0.0), int(unknown or 0)

    # -- segmenting ----------------------------------------------------------
    def _next_key(self, project_id: int) -> str:
        c = self.db.get(DocumentaryProjectCounter, project_id)
        if c is None:
            c = DocumentaryProjectCounter(project_id=project_id, next_scene=1, next_segment=1)
            self.db.add(c)
            self.db.flush()
        key = f"N{c.next_segment:03d}"
        c.next_segment += 1
        return key

    def plan(self, project_id: int) -> dict:
        scenes = list(
            self.db.scalars(
                select(DocumentaryScene).where(DocumentaryScene.project_id == project_id).order_by(DocumentaryScene.order_index)
            )
        )
        if not scenes:
            raise ValidationError("Chưa có storyboard — hãy lập cảnh trước khi chia đoạn narration.")
        existing = {s.text_hash: s for s in self.list(project_id)}
        keep: set[int] = set()
        created = kept = 0
        for order, (text, keys) in enumerate(segment_scenes(scenes, self.policy), start=1):
            h = text_hash(text)
            seg = existing.pop(h, None)
            if seg is not None:
                kept += 1
                seg.order_index, seg.scene_keys = order, keys
            else:
                created += 1
                seg = DocumentaryNarrationSegment(
                    project_id=project_id, segment_key=self._next_key(project_id), order_index=order,
                    text=text, text_hash=h, scene_keys=keys, chars=len(text),
                )
                self.db.add(seg)
            self.db.flush()
            keep.add(seg.id)
        removed = 0
        for seg in self.list(project_id):
            if seg.id not in keep:
                self.db.delete(seg)
                removed += 1
        self.db.commit()
        return {"segments": len(self.list(project_id)), "created": created, "kept": kept, "removed": removed}

    # -- estimate & generate --------------------------------------------------
    def estimate(self, project_id: int, backend_name: str) -> dict:
        backend = get_backend(backend_name)
        pending = [s for s in self.list(project_id) if not self.is_current(s, backend)]
        chars = sum(len(s.text) for s in pending)
        cost = backend.estimate_cost(chars)
        spent, unknown = self.spent_usd(project_id)
        project = self.db.get(DocumentaryProject, project_id)
        return {
            "backend": backend.name,
            "paid": backend.paid,
            "segments_total": len(self.list(project_id)),
            "segments_to_generate": len(pending),
            "segment_keys": [s.segment_key for s in pending],
            "chars": chars,
            "estimated_cost_usd": cost,  # None = price not configured / unknown
            "spent_usd": round(spent, 6),
            "spent_unknown_rows": unknown,
            "budget_usd": project.budget_usd,
        }

    def generate(self, project: DocumentaryProject, backend_name: str, *, only: list[str] | None = None, confirm: bool = False) -> dict:
        backend = get_backend(backend_name)
        segments = self.list(project.id)
        if not segments:
            raise ValidationError("Chưa chia đoạn narration — hãy chạy bước chia đoạn trước.")
        targets = [s for s in segments if (only is None or s.segment_key in only) and not self.is_current(s, backend)]
        if only:
            unknown_keys = set(only) - {s.segment_key for s in segments}
            if unknown_keys:
                raise ValidationError(f"Không có đoạn narration: {sorted(unknown_keys)}")
        est = self.estimate(project.id, backend_name)
        chars = sum(len(s.text) for s in targets)
        cost = backend.estimate_cost(chars)
        if targets and backend.paid and not confirm:
            raise ValidationError(
                f"Backend trả phí '{backend.name}': sẽ tạo {len(targets)} đoạn, {chars} ký tự, chi phí ước tính "
                f"{'chưa biết (chưa cấu hình giá)' if cost is None else f'${cost:.4f}'}. "
                "Xem lại ước tính rồi gửi confirm=true để chạy."
            )
        if cost is not None and project.budget_usd is not None and est["spent_usd"] + cost > project.budget_usd and not confirm:
            raise ValidationError(
                f"Sẽ vượt ngân sách: đã chi ${est['spent_usd']:.4f} + ${cost:.4f} > ${project.budget_usd:.2f}. "
                "Gửi confirm=true nếu vẫn muốn chạy."
            )

        done, skipped, failed = [], len(segments) - len(targets), []
        for seg in targets:
            ck = cache_key_for(seg.text_hash, backend)
            if seg.attempt_key != ck:
                seg.attempts, seg.attempt_key = 0, ck  # new text/voice version: fresh retry budget
            if seg.attempts >= self.policy.max_attempts:
                failed.append({"segment": seg.segment_key, "reason": f"Đã thử {seg.attempts} lần — sửa văn bản hoặc đổi giọng để thử lại."})
                continue
            seg.attempts += 1
            out = self.audio_dir(project.id) / f"{seg.segment_key}_{ck[:8]}{backend.extension}"
            tmp = out.with_name(out.stem + ".tmp" + out.suffix)
            try:
                tmp.parent.mkdir(parents=True, exist_ok=True)
                result = backend.synthesize(seg.text, tmp)
                duration = media.probe_duration(tmp)
                if duration < self.policy.min_audio_sec:
                    raise ValidationError(f"Audio quá ngắn ({duration:.2f}s) — có thể TTS trả file rỗng.")
                tmp.replace(out)
            except (ValidationError, ExternalServiceError, OSError) as exc:
                tmp.unlink(missing_ok=True)
                seg.status, seg.error = "failed", str(exc)[:500]
                self.db.add(DocumentaryUsage(project_id=project.id, kind="tts", provider=backend.name, ref=seg.segment_key, ok=False))
                self.db.commit()
                failed.append({"segment": seg.segment_key, "reason": str(exc)[:300]})
                continue
            seg.audio_path, seg.duration_sec, seg.chars = str(out), duration, result.chars
            seg.provider, seg.voice, seg.cost_usd = backend.name, result.voice, result.cost_usd
            seg.word_stamps = [{"text": w.text, "start": w.start, "end": w.end} for w in result.word_stamps] if result.word_stamps else None
            seg.cache_key, seg.status, seg.error, seg.master_start, seg.master_end = ck, "ready", None, None, None
            self.db.add(
                DocumentaryUsage(project_id=project.id, kind="tts", provider=backend.name, model=result.model,
                                 ref=seg.segment_key, chars=result.chars, cost_usd=result.cost_usd)
            )
            self.db.commit()
            done.append(seg.segment_key)
        return {"generated": done, "skipped_cached": skipped, "failed": failed}

    def master_digest(self, segments: list[DocumentaryNarrationSegment]) -> str:
        return hashlib.sha256(
            ("|".join(s.cache_key or "" for s in segments) + f"|gap={self.policy.gap_sec}").encode("utf-8")
        ).hexdigest()[:16]

    # -- master ----------------------------------------------------------------
    def build_master(self, project_id: int) -> dict:
        segments = self.list(project_id)
        stale = [s.segment_key for s in segments if not self.is_current(s)]
        if not segments or stale:
            raise ValidationError(f"Chưa đủ audio để ghép master — còn thiếu/cũ: {stale or 'chưa có đoạn nào'}.")
        digest = self.master_digest(segments)
        master, meta_path = self.master_path(project_id), self._meta_path(project_id)
        if master.is_file() and meta_path.is_file():
            try:
                if json.loads(meta_path.read_text(encoding="utf-8")).get("hash") == digest and all(s.master_end for s in segments):
                    return {"rebuilt": False, "duration_sec": media.probe_duration(master), "path": str(master)}
            except (json.JSONDecodeError, ValidationError):
                pass
        work = self.audio_dir(project_id) / "_work"
        work.mkdir(parents=True, exist_ok=True)
        gap = work / "gap.wav"
        media.make_silence(gap, self.policy.gap_sec)
        parts, t = [], 0.0
        for i, seg in enumerate(segments):
            wav = work / f"{seg.segment_key}.wav"
            media.to_wav(Path(seg.audio_path), wav)
            d = media.probe_duration(wav)
            seg.master_start, seg.master_end = round(t, 3), round(t + d, 3)
            parts.append(wav)
            t += d
            if i < len(segments) - 1:
                parts.append(gap)
                t += self.policy.gap_sec
        tmp = master.with_name("narration_master.tmp.wav")
        media.concat_wavs(parts, tmp)
        tmp.replace(master)
        total = media.probe_duration(master)
        if abs(total - t) > 0.1:
            raise ValidationError(f"Master lệch độ dài: đo {total:.2f}s, tính {t:.2f}s.")
        meta_path.write_text(json.dumps({"hash": digest, "duration_sec": total}), encoding="utf-8")
        self.db.commit()
        return {"rebuilt": True, "duration_sec": total, "path": str(master)}

    # -- gate 4 (audio part; timing checks are added by alignment) ----------------
    def review(self, project_id: int) -> list[ReviewIssue]:
        segments = self.list(project_id)
        if not segments:
            return [ReviewIssue(code="no_segments", message="Chưa chia đoạn narration.")]
        issues = []
        for s in segments:
            if s.status == "failed":
                issues.append(ReviewIssue(code="segment_failed", message=f"Đoạn {s.segment_key}: lỗi — {s.error}"))
            elif not self.is_current(s):
                issues.append(ReviewIssue(code="segment_not_ready", message=f"Đoạn {s.segment_key}: chưa có audio cho văn bản/giọng hiện tại."))
        if not issues:
            digest = self.master_digest(segments)
            try:
                fresh = json.loads(self._meta_path(project_id).read_text(encoding="utf-8")).get("hash") == digest
            except (OSError, json.JSONDecodeError):
                fresh = False
            if not (self.master_path(project_id).is_file() and fresh):
                issues.append(ReviewIssue(code="no_master", message="Narration master chưa có hoặc đã cũ — hãy ghép lại để nghe duyệt toàn bài."))
        return issues
