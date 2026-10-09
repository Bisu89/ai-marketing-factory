"""Asset registry for a documentary project, plus the manual-generation
loop that replaces paid image APIs:

    scenes needing images --export CSV--> user generates them elsewhere
    --drops files into a folder--> import by scene key --> review/approve.

Nothing here calls a provider or spends money. Cost ladder, in order:
approved asset with the same input hash is reused (no new image), scenes in
one image group share one file, programmatic scenes need no file at all, and
only the remainder is listed in the CSV.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import shutil
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary.models import DocumentaryAsset, DocumentaryScene
from app.modules.documentary.schemas import ReviewIssue

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_FOLDER_FILES = 500
ORIGINS = ("imported", "archival", "ai_manual")
# Header names match the existing zombie / biblical-figures CSV workflow.
CSV_HEADER = [
    "STT",
    "Ten file (filename.png)",
    "Tags (dan khi import)",
    "Prompt day du (copy nguyen vao ChatGPT)",
]
_SCENE_KEY = re.compile(r"^(S\d{3})")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_state(scene: DocumentaryScene, asset: DocumentaryAsset | None) -> str:
    """One word describing whether a scene's visual is ready."""
    if scene.asset_strategy == "programmatic":
        return "programmatic"
    if asset is None:
        return "missing"
    if not Path(asset.path).is_file():
        return "file_missing"
    if asset.approval_status == "rejected":
        return "rejected"
    if asset.origin == "ai_manual" and scene.assigned_hash and scene.input_hash and scene.assigned_hash != scene.input_hash:
        return "stale"
    return "approved" if asset.approval_status == "approved" else "pending"


class AssetService:
    def __init__(self, db: Session, root: Path):
        self.db = db
        self.root = root

    def project_dir(self, project_id: int) -> Path:
        return self.root / "_documentary" / f"project_{project_id}" / "assets"

    # -- registry ----------------------------------------------------------
    def list(self, project_id: int) -> list[DocumentaryAsset]:
        return list(
            self.db.scalars(
                select(DocumentaryAsset).where(DocumentaryAsset.project_id == project_id).order_by(DocumentaryAsset.id)
            )
        )

    def get(self, project_id: int, asset_id: int) -> DocumentaryAsset:
        a = self.db.get(DocumentaryAsset, asset_id)
        if a is None or a.project_id != project_id:
            raise NotFoundError("asset", asset_id)
        return a

    def import_file(
        self,
        project_id: int,
        src: Path,
        *,
        origin: str = "imported",
        license: str | None = None,
        attribution: str | None = None,
        source_url: str | None = None,
        tags: list[str] | None = None,
        prompt: str | None = None,
        model: str | None = None,
        input_hash: str | None = None,
    ) -> tuple[DocumentaryAsset, bool]:
        """-> (asset, created). Same bytes already in the project return the
        existing row instead of a duplicate (content-hash dedupe)."""
        if origin not in ORIGINS:
            raise ValidationError(f"origin không hợp lệ: {origin!r}")
        src = Path(src)
        if not src.is_file():
            raise ValidationError(f"Không tìm thấy file ảnh: {src}")
        ext = src.suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            raise ValidationError(f"Định dạng không được hỗ trợ: {ext or '(không có đuôi)'} — dùng png/jpg/webp.")
        if src.stat().st_size > MAX_IMAGE_BYTES:
            raise ValidationError(f"Ảnh quá lớn (> {MAX_IMAGE_BYTES // (1024 * 1024)} MB): {src.name}")
        try:
            with Image.open(src) as im:
                im.verify()
            with Image.open(src) as im:
                width, height = im.size
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError(f"File không phải ảnh hợp lệ: {src.name}") from exc

        digest = sha256_file(src)
        existing = self.db.scalars(
            select(DocumentaryAsset).where(
                DocumentaryAsset.project_id == project_id, DocumentaryAsset.content_hash == digest
            )
        ).first()
        if existing is not None:
            return existing, False

        dest_dir = self.project_dir(project_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{digest[:16]}{ext}"  # generated name only: user input never builds a path
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        tmp.replace(dest)

        asset = DocumentaryAsset(
            project_id=project_id,
            path=str(dest),
            type="image",
            origin=origin,
            source_url=source_url,
            license=license,
            attribution=attribution,
            prompt=prompt,
            model=model,
            input_hash=input_hash,
            content_hash=digest,
            width=width,
            height=height,
            tags=tags or [],
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset, True

    def approve(self, project_id: int, asset_id: int) -> DocumentaryAsset:
        a = self.get(project_id, asset_id)
        if not Path(a.path).is_file():
            raise ValidationError("File ảnh không còn tồn tại trên đĩa — hãy thay ảnh khác.")
        if a.origin == "archival":
            lic = (a.license or "").strip().lower()
            if not lic or lic in ("unknown", "không rõ", "khong ro"):
                raise ValidationError(
                    "Ảnh tư liệu cần ghi rõ giấy phép sử dụng (license) trước khi duyệt — "
                    "ảnh công khai trên mạng không mặc định được phép dùng thương mại."
                )
            if not (a.attribution or "").strip():
                raise ValidationError("Ảnh tư liệu cần ghi nguồn/tác giả (attribution) trước khi duyệt.")
        a.approval_status = "approved"
        self.db.commit()
        self.db.refresh(a)
        return a

    def reject(self, project_id: int, asset_id: int) -> DocumentaryAsset:
        a = self.get(project_id, asset_id)
        a.approval_status = "rejected"
        self.db.commit()
        self.db.refresh(a)
        return a

    def update_metadata(self, project_id: int, asset_id: int, changes: dict) -> DocumentaryAsset:
        a = self.get(project_id, asset_id)
        for k in ("license", "attribution", "source_url", "tags"):
            if k in changes:
                setattr(a, k, changes[k])
        if a.approval_status == "approved":
            a.approval_status = "pending"  # metadata changed: needs a fresh look
        self.db.commit()
        self.db.refresh(a)
        return a

    # -- scene <-> asset -----------------------------------------------------
    def _group(self, scene: DocumentaryScene) -> list[DocumentaryScene]:
        if not scene.image_group:
            return [scene]
        return list(
            self.db.scalars(
                select(DocumentaryScene).where(
                    DocumentaryScene.project_id == scene.project_id, DocumentaryScene.image_group == scene.image_group
                )
            )
        )

    def assign(self, project_id: int, scene_id: int, asset_id: int | None) -> list[DocumentaryScene]:
        scene = self.db.get(DocumentaryScene, scene_id)
        if scene is None or scene.project_id != project_id:
            raise NotFoundError("scene", scene_id)
        if scene.asset_strategy != "image":
            raise ValidationError("Cảnh này dùng đồ họa lập trình, không cần ảnh. Đổi preset trước nếu muốn gán ảnh.")
        if asset_id is not None:
            self.get(project_id, asset_id)
        group = self._group(scene)
        for s in group:
            s.asset_id = asset_id
            s.assigned_hash = s.input_hash if asset_id is not None else None
        self.db.commit()
        return group

    def resolve_reuse(self, project_id: int) -> int:
        """Cache hit: an approved asset made for the same input hash is
        assigned instead of asking for a new image. -> number of groups
        filled this way."""
        approved = {
            a.input_hash: a
            for a in self.list(project_id)
            if a.approval_status == "approved" and a.input_hash and Path(a.path).is_file()
        }
        scenes = list(
            self.db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == project_id))
        )
        by_id = {a.id: a for a in self.list(project_id)}
        filled = 0
        for head in (s for s in scenes if s.asset_strategy == "image" and s.image_group == s.scene_key):
            if asset_state(head, by_id.get(head.asset_id)) in ("approved", "pending"):
                continue
            hit = approved.get(head.input_hash)
            if hit is not None:
                for s in self._group(head):
                    s.asset_id, s.assigned_hash = hit.id, s.input_hash
                filled += 1
        self.db.commit()
        return filled

    # -- manual generation loop ------------------------------------------------
    def needing_images(self, project_id: int) -> list[DocumentaryScene]:
        by_id = {a.id: a for a in self.list(project_id)}
        scenes = list(
            self.db.scalars(
                select(DocumentaryScene)
                .where(DocumentaryScene.project_id == project_id)
                .order_by(DocumentaryScene.order_index)
            )
        )
        return [
            s
            for s in scenes
            if s.asset_strategy == "image"
            and s.image_group == s.scene_key
            and asset_state(s, by_id.get(s.asset_id)) in ("missing", "rejected", "stale", "file_missing")
        ]

    @staticmethod
    def csv_filename(scene: DocumentaryScene) -> str:
        return f"{scene.scene_key}_{scene.section_kind}.png"

    def export_csv(self, project_id: int) -> tuple[str, dict]:
        reused = self.resolve_reuse(project_id)
        heads = self.needing_images(project_id)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(CSV_HEADER)
        for i, h in enumerate(heads, start=1):
            w.writerow([i, self.csv_filename(h), f"{h.section_kind}, {h.visual_preset}", h.visual_objective])
        # BOM so Excel/ChatGPT-side tools read the Vietnamese correctly (same as the existing CSVs).
        return "﻿" + buf.getvalue(), {"to_generate": len(heads), "reused_from_cache": reused}

    def import_folder(self, project_id: int, folder: Path) -> dict:
        folder = Path(folder)
        if not folder.is_dir():
            raise ValidationError(f"Không tìm thấy thư mục: {folder}")
        files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        if len(files) > MAX_FOLDER_FILES:
            raise ValidationError(f"Thư mục có quá nhiều ảnh (> {MAX_FOLDER_FILES}).")
        heads = {
            s.scene_key: s
            for s in self.db.scalars(
                select(DocumentaryScene).where(
                    DocumentaryScene.project_id == project_id, DocumentaryScene.asset_strategy == "image"
                )
            )
            if s.image_group == s.scene_key
        }
        report = {"imported": [], "duplicate": [], "unmatched": [], "failed": []}
        for f in files:
            m = _SCENE_KEY.match(f.stem)
            head = heads.get(m.group(1)) if m else None
            if head is None:
                report["unmatched"].append(f.name)
                continue
            try:
                asset, created = self.import_file(
                    project_id,
                    f,
                    origin="ai_manual",
                    prompt=head.visual_objective,
                    model="manual (user-generated)",
                    input_hash=head.input_hash,
                    tags=[head.section_kind, head.visual_preset],
                )
            except ValidationError as exc:
                report["failed"].append({"file": f.name, "reason": str(exc)})
                continue
            for s in self._group(head):
                s.asset_id, s.assigned_hash = asset.id, s.input_hash
            self.db.commit()
            report["imported" if created else "duplicate"].append(f.name)
        return report

    # -- gate 3 --------------------------------------------------------------
    def review(self, project_id: int) -> list[ReviewIssue]:
        scenes = list(
            self.db.scalars(
                select(DocumentaryScene)
                .where(DocumentaryScene.project_id == project_id)
                .order_by(DocumentaryScene.order_index)
            )
        )
        if not scenes:
            return [ReviewIssue(code="no_scenes", message="Chưa có storyboard (chưa lập cảnh từ kịch bản).")]
        by_id = {a.id: a for a in self.list(project_id)}
        messages = {
            "missing": "chưa có ảnh",
            "pending": "ảnh chưa được duyệt",
            "rejected": "ảnh đã bị từ chối",
            "stale": "ảnh được tạo cho mô tả cũ — mô tả cảnh đã đổi",
            "file_missing": "file ảnh không còn trên đĩa",
        }
        issues = []
        for s in scenes:
            state = asset_state(s, by_id.get(s.asset_id))
            if state in messages:
                issues.append(ReviewIssue(code=f"asset_{state}", message=f"Cảnh {s.scene_key}: {messages[state]}."))
        return issues
