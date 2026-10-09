"""Export bundle: everything needed to publish, and to show later where each fact and image came from.

An export is only possible after gate 5 (a final render that passed QC and still matches the data).
The bundle is a plain folder:

  video.mp4          the validated final render (copied, never re-encoded)
  subtitles.srt      the reviewed subtitles
  credits.json/.txt  every image used: origin, licence, attribution, source URL, scenes, prompt (AI)
  sources.json       sources and claims (status, uncertainty note, which source supports which claim)
  script.md          the approved script with claim references
  timeline.json      scenes with start/end and the provenance of each timing
  description.txt    a draft video description: chapters, sources, image credits
  manifest.json      project/render facts and a SHA-256 of every file above

Nothing is published and no file outside the folder is touched.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.modules.documentary.models import (
    DocumentaryAsset,
    DocumentaryClaim,
    DocumentaryClaimSource,
    DocumentaryExport,
    DocumentaryProject,
    DocumentaryScene,
    DocumentarySceneTiming,
    DocumentarySource,
)
from app.modules.documentary.render import RenderService
from app.modules.documentary.schemas import SECTION_LABELS_VI
from app.modules.documentary.script import ScriptService
from app.modules.documentary.timeline import TimelineService

NEEDS_REVIEW_LICENCES = ("CC BY-SA", "FAL", "GFDL", "CC BY-NC", "CC BY-ND")


def slug(text: str, limit: int = 48) -> str:
    folded = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    ascii_ = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    return (re.sub(r"[^a-z0-9]+", "_", ascii_).strip("_") or "documentary")[:limit]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_clock(t: float) -> str:
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


class ExportService:
    def __init__(self, db: Session, root: Path):
        self.db = db
        self.root = root

    def export_dir(self, project_id: int) -> Path:
        return self.root / "_documentary" / f"project_{project_id}" / "export"

    def list(self, project_id: int) -> list[DocumentaryExport]:
        return list(
            self.db.scalars(
                select(DocumentaryExport).where(DocumentaryExport.project_id == project_id).order_by(DocumentaryExport.id.desc())
            )
        )

    def get(self, project_id: int, export_id: int) -> DocumentaryExport:
        e = self.db.get(DocumentaryExport, export_id)
        if e is None or e.project_id != project_id:
            raise ValidationError("Không tìm thấy bản xuất này.")
        return e

    # -- the bundle ---------------------------------------------------------------------------
    def export(self, project: DocumentaryProject) -> DocumentaryExport:
        pid = project.id
        render = RenderService(self.db, self.root)
        review = render.final_review(pid)
        if not review.ok:
            raise ValidationError("Chưa thể xuất: " + "; ".join(i.message for i in review.issues))
        job = next(j for j in render.list(pid) if j.kind == "final" and j.status == "succeeded")
        video = Path(job.output_path)

        folder = self.export_dir(pid) / f"{slug(project.title)}_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        folder.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(video, folder / "video.mp4")
        timeline = TimelineService(self.db, self.root)
        (folder / "subtitles.srt").write_text(timeline.srt(pid), encoding="utf-8")

        assets, credits = self._credits(pid)
        music = self._music(job)
        (folder / "credits.json").write_text(json.dumps({"images": credits, "music": music}, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "credits.txt").write_text(self._credits_txt(credits, music), encoding="utf-8")
        sources = self._sources(pid)
        (folder / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "script.md").write_text(self._script_md(project, sources), encoding="utf-8")
        tl = self._timeline(pid)
        (folder / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "description.txt").write_text(self._description(project, tl, sources, credits, music), encoding="utf-8")

        warnings = self._warnings(credits, tl, job, music)
        files = {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in sorted(folder.iterdir())}
        manifest = {
            "generator": "Vox Documentary Factory export v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project": {"id": pid, "title": project.title, "topic": project.topic, "language": project.language, "state": project.state},
            "versions": {
                "research": project.research_version, "script": project.script_version, "storyboard": project.storyboard_version,
                "narration": project.narration_version, "render": project.render_version,
            },
            "render": {"job_id": job.id, "input_hash": job.input_hash, "params": job.params, "duration_sec": job.duration_sec, "qc": job.qc},
            "warnings": warnings,
            "files": files,
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        files["manifest.json"] = {"sha256": sha256_file(folder / "manifest.json"), "bytes": (folder / "manifest.json").stat().st_size}

        row = DocumentaryExport(project_id=pid, render_job_id=job.id, path=str(folder.resolve()), files=files, warnings=warnings)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # -- pieces -----------------------------------------------------------------------------------
    def _credits(self, pid: int) -> tuple[dict, list[dict]]:
        scenes = list(self.db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == pid).order_by(DocumentaryScene.order_index)))
        by_asset: dict[int, list[str]] = {}
        for s in scenes:
            if s.asset_id:
                by_asset.setdefault(s.asset_id, []).append(s.scene_key)
        assets = {a.id: a for a in self.db.scalars(select(DocumentaryAsset).where(DocumentaryAsset.project_id == pid))}
        credits = []
        for aid, keys in by_asset.items():
            a = assets[aid]
            credits.append(
                {
                    "asset_id": a.id, "origin": a.origin, "license": a.license, "attribution": a.attribution, "source_url": a.source_url,
                    "scenes": keys, "approval": a.approval_status, "content_sha256": a.content_hash,
                    "prompt": a.prompt if a.origin == "ai_manual" else None,
                    "label": "Minh họa AI (không phải tư liệu thời đó)" if a.origin == "ai_manual" else None,
                }
            )
        return assets, credits

    @staticmethod
    def _music(job) -> dict | None:
        """The background track of the exported render, if any (its credit is the user's to supply)."""
        p = job.params or {}
        if not p.get("music_path"):
            return None
        f = Path(p["music_path"])
        return {"file": f.name, "credit": p.get("music_credit"), "level_db": p.get("music_db"), "sha256": sha256_file(f) if f.is_file() else None}

    @staticmethod
    def _credits_txt(credits: list[dict], music: dict | None = None) -> str:
        lines = ["HÌNH ẢNH VÀ GHI CÔNG", ""]
        for c in credits:
            kind = {"archival": "Tư liệu", "ai_manual": "Minh họa AI", "imported": "Ảnh tự nhập"}.get(c["origin"], c["origin"])
            parts = [f"[{kind}]", c["attribution"] or "(không ghi tác giả)", c["license"] or "(không ghi giấy phép)"]
            lines.append(" · ".join(parts) + f"  — cảnh {', '.join(c['scenes'])}")
            if c["source_url"]:
                lines.append(f"    {c['source_url']}")
        if music:
            lines += ["", "NHẠC NỀN", f"{music['file']} — {music['credit'] or '(chưa ghi giấy phép/ghi công)'}"]
        return "\n".join(lines) + "\n"

    def _sources(self, pid: int) -> dict:
        srcs = list(self.db.scalars(select(DocumentarySource).where(DocumentarySource.project_id == pid).order_by(DocumentarySource.id)))
        claims = list(self.db.scalars(select(DocumentaryClaim).where(DocumentaryClaim.project_id == pid).order_by(DocumentaryClaim.id)))
        links: dict[int, list[int]] = {}
        for link in self.db.scalars(select(DocumentaryClaimSource)):
            links.setdefault(link.claim_id, []).append(link.source_id)
        return {
            "sources": [
                {"id": s.id, "title": s.title, "url": s.url, "publisher": s.publisher, "author": s.author,
                 "published_date": s.published_date.isoformat() if s.published_date else None,
                 "accessed_date": s.accessed_date.isoformat() if s.accessed_date else None, "excerpt": s.excerpt, "notes": s.notes}
                for s in srcs
            ],
            "claims": [
                {"id": c.id, "text": c.text, "status": c.status, "uncertainty_note": c.uncertainty_note, "source_ids": sorted(links.get(c.id, []))}
                for c in claims
            ],
        }

    def _script_md(self, project: DocumentaryProject, sources: dict) -> str:
        row = ScriptService(self.db).current_row(project.id)
        out = [f"# {project.title}", "", f"_Chủ đề: {project.topic}_", ""]
        for sec in (row.sections if row else []):
            out += [f"## {SECTION_LABELS_VI.get(sec['kind'], sec['heading'])}", ""]
            for p in sec["paragraphs"]:
                refs = " ".join(f"[c{c}]" for c in p["claim_ids"])
                out += [f"{p['text']} {refs}".rstrip(), ""]
        out += ["---", "Chú thích [cN]: xem sources.json (khẳng định N và nguồn hỗ trợ).", ""]
        return "\n".join(out)

    def _timeline(self, pid: int) -> list[dict]:
        scenes = {s.scene_key: s for s in self.db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == pid))}
        rows = []
        for t in self.db.scalars(select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == pid).order_by(DocumentarySceneTiming.order_index)):
            s = scenes[t.scene_key]
            rows.append(
                {"scene": t.scene_key, "section": s.section_kind, "preset": s.visual_preset, "start": t.start, "end": t.end,
                 "timing_source": t.source, "timing_coverage": t.coverage, "needs_review": t.needs_review, "asset_id": s.asset_id,
                 "claim_ids": s.claim_ids, "narration": s.narration_text}
            )
        return rows

    def _description(self, project: DocumentaryProject, tl: list[dict], sources: dict, credits: list[dict], music: dict | None = None) -> str:
        seen, chapters = set(), []
        for r in tl:
            if r["section"] not in seen:
                seen.add(r["section"])
                chapters.append(f"{fmt_clock(r['start'])} {SECTION_LABELS_VI.get(r['section'], r['section'])}")
        lines = [project.title, "", project.topic, "", "Chương:"] + chapters + ["", "NGUỒN"]
        grouped: dict[str, list[dict]] = {}
        for s in sources["sources"]:  # several excerpts of one page are one source line
            grouped.setdefault(s["url"] or f"#{s['id']}", []).append(s)
        for url, group in grouped.items():
            base = group[0]["title"].split(" (")[0]
            parts = [g["title"].split(" (", 1)[1].rstrip(")") for g in group if " (" in g["title"]]
            line = f"- {base}" + (f" ({'; '.join(parts)})" if len(group) > 1 and parts else "")
            line += (f" — {url}" if group[0]["url"] else "") + (f" (truy cập {group[0]['accessed_date']})" if group[0]["accessed_date"] else "")
            lines.append(line)
        disputed = [c for c in sources["claims"] if c["status"] == "disputed"]
        if disputed:
            lines += ["", "LƯU Ý: một số con số/diễn giải còn tranh cãi giữa các nguồn (đã nêu trong video)."]
        lines += ["", "HÌNH ẢNH"]
        for c in credits:
            if c["origin"] == "archival":
                lines.append(f"- {c['attribution'] or 'Không rõ tác giả'}, {c['license'] or 'không rõ giấy phép'}" + (f" — {c['source_url']}" if c["source_url"] else ""))
        if any(c["origin"] == "ai_manual" for c in credits):
            lines.append("- Các cảnh gắn nhãn \"Minh họa AI\" là hình minh họa do AI tạo, không phải tư liệu thời đó.")
        if music and music["credit"]:
            lines += ["", "NHẠC", f"- {music['credit']}"]
        return "\n".join(lines) + "\n"

    def _warnings(self, credits: list[dict], tl: list[dict], job, music: dict | None = None) -> list[dict]:
        w: list[dict] = []
        if music and not music["credit"]:
            w.append({"code": "music_no_credit", "message": f"Có nhạc nền ({music['file']}) nhưng chưa ghi giấy phép/ghi công — hãy bổ sung trước khi đăng."})
        for c in credits:
            lic = (c["license"] or "")
            if c["origin"] == "archival" and (not lic or any(lic.startswith(p) for p in NEEDS_REVIEW_LICENCES)):
                w.append({"code": "licence_needs_review", "message": f"Ảnh #{c['asset_id']} (cảnh {', '.join(c['scenes'])}): giấy phép '{lic or 'không rõ'}' cần đọc kỹ trước khi dùng thương mại."})
            if c["approval"] != "approved":
                w.append({"code": "asset_not_approved", "message": f"Ảnh #{c['asset_id']} chưa ở trạng thái đã duyệt."})
        if any(c["origin"] == "ai_manual" for c in credits):
            w.append({"code": "ai_images", "message": "Có ảnh AI: cân nhắc khai báo nội dung tổng hợp khi đăng (kiểm tra chính sách nền tảng hiện hành)."})
        est = [r["scene"] for r in tl if r["needs_review"]]
        if est:
            w.append({"code": "timing_unverified", "message": f"{len(est)} cảnh có timing ước lượng/khớp thấp: {', '.join(est[:8])}."})
        for i in (job.qc or {}).get("warnings", []):
            if i.get("code") not in ("timing_unverified",):
                w.append({"code": i.get("code", "qc"), "message": i.get("message", "")})
        return w

