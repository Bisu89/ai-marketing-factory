"""Storyboard planning: approved script -> scenes.

Scene boundaries follow sentences and paragraphs, never a fixed number of
seconds. Visual decisions come from an explicit, editable `StoryboardPolicy`
(not buried constants), and follow a cost ladder: programmatic graphics
(free) before an image, one image shared by neighbouring scenes before a new
one, and AI video never (off by default; a flag, not an assumption).

Re-planning is non-destructive: a scene whose narration is unchanged keeps
its row, scene_key, assigned asset and any manual edits. Only genuinely new or
changed narration gets a new scene, so editing one paragraph never disturbs
(or re-generates assets for) the others.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary.models import (
    DocumentaryProject,
    DocumentaryProjectCounter,
    DocumentaryScene,
)
from app.modules.documentary.schemas import ScriptSection
from app.modules.documentary.script import SYLLABLES_PER_SECOND, ScriptService

PRESETS = (
    "NewspaperStack", "ArchivalPortrait", "MapZoom", "TimelineBuild", "BigNumber",
    "EvidenceBoard", "PhotoKenBurns", "HeadlineImpact", "SplitComparison",
)
# Presets drawn entirely by code (Remotion): no image file needed.
PROGRAMMATIC_PRESETS = frozenset({"MapZoom", "TimelineBuild", "BigNumber", "EvidenceBoard", "HeadlineImpact"})


@dataclass(frozen=True)
class StoryboardPolicy:
    min_scene_words: int = 18
    max_scene_words: int = 45
    tiny_paragraph_words: int = 12
    max_scenes_per_image: int = 3
    allow_ai_video: bool = False  # AI video is never chosen unless a human flips this
    image_style: str = (
        "muted archival documentary illustration, grayscale-leaning warm tones, paper grain, "
        "horizontal 16:9, no text, no lettering, no watermark"
    )
    map_words: tuple[str, ...] = (
        "bản đồ", "biên giới", "lãnh thổ", "hải trình", "tuyến đường", "quần đảo", "eo biển",
    )  # deliberately not "thành phố"/"vùng": they occur in almost every sentence
    big_number_pattern: str = r"\b\d[\d.,]*\s*(?:%|phần trăm|người|tấn|triệu|nghìn|ngàn|tỷ|km|mét|con tàu|binh sĩ)"
    # A year is 'năm 330' (3 digits need the word) or a 4-digit 1000-2099 -- never a piece of a
    # grouped number: the '000' in '7.000' used to count as a year.
    year_pattern: str = r"(?<![\d.,])(?:năm\s+\d{3}|1\d{3}|20\d{2})(?!\d|[.,]\d)"


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def words(text: str) -> int:
    return len(text.split())


def narration_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def input_hash(prompt: str, orientation: str = "16:9") -> str:
    normalized = re.sub(r"\s+", " ", prompt.strip().lower())
    return hashlib.sha256(f"{orientation}|{normalized}".encode("utf-8")).hexdigest()[:16]


@dataclass
class PlannedScene:
    section_kind: str
    paragraph_id: str
    text: str
    claim_ids: list[int] = field(default_factory=list)


def plan_units(sections: list[ScriptSection], policy: StoryboardPolicy) -> list[PlannedScene]:
    """Pure: sections -> ordered scene units. Tiny paragraphs (transition
    lines) are folded into the next paragraph of the same section so they
    do not get a scene of their own."""
    units: list[PlannedScene] = []
    for section in sections:
        carry_text, carry_claims = "", []
        for pi, para in enumerate(section.paragraphs):
            text = (carry_text + " " + para.text).strip()
            claims = sorted(set(carry_claims + para.claim_ids))
            last = pi == len(section.paragraphs) - 1
            if words(para.text) < policy.tiny_paragraph_words and not last:
                carry_text, carry_claims = text, claims
                continue
            carry_text, carry_claims = "", []
            pid = f"{section.kind}-{pi + 1}"
            chunks: list[str] = []
            cur: list[str] = []
            for sentence in split_sentences(text) or [text]:
                if cur and words(" ".join(cur + [sentence])) > policy.max_scene_words:
                    chunks.append(" ".join(cur))
                    cur = []
                cur.append(sentence)
                if words(" ".join(cur)) >= policy.min_scene_words:
                    chunks.append(" ".join(cur))
                    cur = []
            if cur:
                if chunks and words(" ".join(cur)) < policy.tiny_paragraph_words // 2 + 2:
                    chunks[-1] += " " + " ".join(cur)  # don't leave a stub scene
                else:
                    chunks.append(" ".join(cur))
            for c in chunks:
                units.append(PlannedScene(section.kind, pid, c, claims))
    return units


def classify(unit: PlannedScene, policy: StoryboardPolicy) -> tuple[str, str]:
    """-> (visual_preset, asset_strategy). Rule-based and explainable."""
    t = unit.text.lower()
    if unit.section_kind == "timeline" or len(re.findall(policy.year_pattern, t)) >= 2:
        return "TimelineBuild", "programmatic"
    if re.search(policy.big_number_pattern, t):
        return "BigNumber", "programmatic"
    if any(w in t for w in policy.map_words):
        return "MapZoom", "programmatic"
    if unit.section_kind == "evidence":
        return "EvidenceBoard", "programmatic"
    if unit.section_kind == "turning_point" and words(unit.text) <= 25:
        return "HeadlineImpact", "programmatic"
    if unit.section_kind == "hook":
        return "PhotoKenBurns", "image"
    return "PhotoKenBurns", "image"


def image_prompt(unit_text: str, policy: StoryboardPolicy) -> str:
    first = split_sentences(unit_text)[0] if unit_text.strip() else unit_text
    return f"Historical documentary still illustrating: {first} Style: {policy.image_style}."


class StoryboardService:
    def __init__(self, db: Session, policy: StoryboardPolicy | None = None):
        self.db = db
        self.policy = policy or StoryboardPolicy()

    # -- reading -----------------------------------------------------------
    def list(self, project_id: int) -> list[DocumentaryScene]:
        return list(
            self.db.scalars(
                select(DocumentaryScene)
                .where(DocumentaryScene.project_id == project_id)
                .order_by(DocumentaryScene.order_index)
            )
        )

    def get(self, project_id: int, scene_id: int) -> DocumentaryScene:
        s = self.db.get(DocumentaryScene, scene_id)
        if s is None or s.project_id != project_id:
            raise NotFoundError("scene", scene_id)
        return s

    def _next_key(self, project_id: int) -> str:
        counter = self.db.get(DocumentaryProjectCounter, project_id)
        if counter is None:
            counter = DocumentaryProjectCounter(project_id=project_id, next_scene=1)
            self.db.add(counter)
            self.db.flush()
        key = f"S{counter.next_scene:03d}"
        counter.next_scene += 1
        return key

    # -- planning ----------------------------------------------------------
    def plan(self, project: DocumentaryProject) -> dict:
        """Create/refresh scenes from the current script. Requires a script
        that already passed factual review."""
        scripts = ScriptService(self.db)
        review = scripts.review(project.id)
        if not review.ok:
            raise ValidationError(
                "Cần một kịch bản đã qua kiểm tra nguồn trước khi lập storyboard: "
                + "; ".join(i.message for i in review.issues)
            )
        row = scripts.current_row(project.id)
        sections = [ScriptSection.model_validate(s) for s in row.sections]
        units = plan_units(sections, self.policy)

        existing = {s.narration_hash: s for s in self.list(project.id)}
        keep: set[int] = set()
        created = kept = 0
        groups: dict[str, list[DocumentaryScene]] = {}
        for order, u in enumerate(units, start=1):
            scene = existing.pop(narration_hash(u.text), None)
            if scene is not None:
                kept += 1
                scene.order_index, scene.section_kind, scene.claim_ids = order, u.section_kind, u.claim_ids
            else:
                created += 1
                scene = self._new_scene(project.id, order, u)
                self.db.add(scene)
            self.db.flush()
            keep.add(scene.id)
            groups.setdefault(u.paragraph_id, []).append(scene)

        removed = 0
        for s in self.list(project.id):
            if s.id not in keep:
                self.db.delete(s)
                removed += 1
        self._assign_image_groups(groups)
        self.db.commit()
        scenes = self.list(project.id)
        return {
            "scenes": len(scenes),
            "created": created,
            "kept": kept,
            "removed": removed,
            "image_groups": len({s.image_group for s in scenes if s.image_group}),
            "programmatic": sum(1 for s in scenes if s.asset_strategy == "programmatic"),
        }

    def _new_scene(self, project_id: int, order: int, u: PlannedScene) -> DocumentaryScene:
        preset, strategy = classify(u, self.policy)
        objective = u.text if strategy == "programmatic" else image_prompt(u.text, self.policy)
        return DocumentaryScene(
            project_id=project_id,
            scene_key=self._next_key(project_id),
            order_index=order,
            section_kind=u.section_kind,
            narration_text=u.text,
            narration_hash=narration_hash(u.text),
            claim_ids=u.claim_ids,
            visual_objective=objective,
            visual_preset=preset,
            asset_strategy=strategy,
            input_hash=input_hash(objective) if strategy == "image" else None,
            expected_duration=round(words(u.text) / SYLLABLES_PER_SECOND, 2),
            on_screen_text=[],
            sfx_cues=[],
        )

    def _assign_image_groups(self, groups: dict[str, list[DocumentaryScene]]) -> None:
        """Neighbouring image scenes of one paragraph share one image
        (max_scenes_per_image), so a long paragraph never costs N images.
        Followers mirror the head's objective/hash/asset unless hand-edited."""
        cap = self.policy.max_scenes_per_image
        for scenes in groups.values():
            imgs = [s for s in scenes if s.asset_strategy == "image"]
            for i in range(0, len(imgs), cap):
                chunk = imgs[i : i + cap]
                head = chunk[0]
                for s in chunk:
                    s.image_group = head.scene_key
                    if s is not head and not s.user_edited:
                        s.visual_objective, s.input_hash = head.visual_objective, head.input_hash
                        s.asset_id, s.assigned_hash = head.asset_id, head.assigned_hash
            for s in scenes:
                if s.asset_strategy != "image":
                    s.image_group = None

    # -- manual edit -------------------------------------------------------
    def update(self, project_id: int, scene_id: int, changes: dict) -> DocumentaryScene:
        s = self.get(project_id, scene_id)
        if "visual_preset" in changes:
            if changes["visual_preset"] not in PRESETS:
                raise ValidationError(f"Preset không hợp lệ: {changes['visual_preset']!r}")
            s.visual_preset = changes["visual_preset"]
            s.asset_strategy = "programmatic" if s.visual_preset in PROGRAMMATIC_PRESETS else "image"
        objective_changed = "visual_objective" in changes and changes["visual_objective"] != s.visual_objective
        if "visual_objective" in changes:
            s.visual_objective = changes["visual_objective"]
        if "on_screen_text" in changes:
            s.on_screen_text = changes["on_screen_text"]
        if "motion_notes" in changes:
            s.motion_notes = changes["motion_notes"]
        if "sfx_cues" in changes:
            s.sfx_cues = changes["sfx_cues"]
        s.user_edited = True
        if s.asset_strategy == "image":
            s.input_hash = input_hash(s.visual_objective)
            if objective_changed and s.image_group and s.image_group != s.scene_key:
                s.image_group = s.scene_key  # a follower with its own description needs its own image
            elif objective_changed and s.image_group == s.scene_key:
                for f in self.db.scalars(
                    select(DocumentaryScene).where(
                        DocumentaryScene.project_id == project_id,
                        DocumentaryScene.image_group == s.scene_key,
                        DocumentaryScene.id != s.id,
                    )
                ):
                    if not f.user_edited:
                        f.visual_objective, f.input_hash = s.visual_objective, s.input_hash
        else:
            s.input_hash, s.assigned_hash, s.asset_id, s.image_group = None, None, None, None
        self.db.commit()
        self.db.refresh(s)
        return s
