"""Render manifest: the single JSON the Remotion composition draws from.

Everything visual is derived from data that already passed review: the scene
timeline (real audio timing), approved assets, subtitles and the claim status
behind each scene. On-screen text that the user did not write is *derived from
the narration itself* (years, numbers, sentences, proper nouns) -- never
invented -- and each piece is cued to the moment its words are spoken.

The input hash covers the manifest, the audio master and the Remotion source,
so unchanged inputs never trigger a new render.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.modules.documentary.alignment import fold
from app.modules.documentary.assets import asset_state
from app.modules.documentary.models import (
    DocumentaryAsset,
    DocumentaryClaim,
    DocumentaryProject,
    DocumentaryScene,
    DocumentarySceneTiming,
    DocumentarySubtitle,
)
from app.modules.documentary.narration import NarrationService
from app.modules.documentary.schemas import ReviewIssue
from app.modules.documentary.storyboard import PRESETS, StoryboardPolicy

FPS = 30
WIDTH, HEIGHT = 1920, 1080
FADE_FRAMES = 6
STAGGER = 9
# Presets that draw only data derived from the narration: with none, they would render empty.
DATA_PRESETS = frozenset({"TimelineBuild", "BigNumber", "MapZoom"})
# Bump when the render/mux pipeline changes in a way that alters the output file, so cached
# renders from the old pipeline are not reused.
THEMES = ("collage", "cinematic")
PIPELINE_VERSION = 3
MUSIC_EXTENSIONS = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
MAX_MUSIC_BYTES = 100 * 1024 * 1024
REMOTION_DIR = Path(__file__).resolve().parents[4] / "remotion"

_UNIT_AFTER_YEAR = re.compile(r"^\s*(người|tấn|km|mét|triệu|nghìn|ngàn|tỷ|%|phần trăm|con tàu|binh sĩ|lính|quân|năm)\b", re.I)
_YEAR = re.compile(r"(?<![\d.,])(\d{3,4})(?![\d.,]\d)")
_SENT = re.compile(r"(?<=[.!?…])\s+")
_MAGNITUDE = {"triệu", "nghìn", "ngàn", "tỷ"}


@dataclass(frozen=True)
class RenderParams:
    kind: str = "preview"  # preview | final
    scale: float = 0.5
    seconds: float | None = None
    burn_subtitles: bool = True
    grayscale: bool = True
    normalize_audio: bool = True
    theme: str = "collage"  # collage (paper cut-outs) | cinematic (full-bleed paintings, gold type)
    music_path: str | None = None  # optional background track the user supplies (looped, ducked under the voice)
    music_db: float = -24.0  # level of the music before ducking
    music_credit: str | None = None  # licence/credit line for the track, shown in the export

    def to_json(self) -> dict:
        return {
            "kind": self.kind, "scale": self.scale, "seconds": self.seconds, "theme": self.theme,
            "music_path": self.music_path, "music_db": self.music_db, "music_credit": self.music_credit,
            "burn_subtitles": self.burn_subtitles, "grayscale": self.grayscale, "normalize_audio": self.normalize_audio,
        }


# -- overlay text derived from the narration itself ----------------------------------------
def _clip(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def _sentences(narration: str) -> list[str]:
    return [s.strip() for s in _SENT.split(narration.strip()) if s.strip()]


def proper_noun(narration: str) -> str | None:
    """First run of capitalised words that is not just a sentence's first word
    (e.g. 'Sultan Mehmed Đệ Nhị', 'Bosphorus'). Token-based: a character range like
    À-Ỹ would also match lower-case Vietnamese letters."""
    tokens = narration.split()
    run: list[str] = []
    sentence_start = True
    for tok in tokens:
        bare = tok.strip(".,;:!?…\"'()[]“”")
        starts_sentence, sentence_start = sentence_start, tok.endswith((".", "!", "?", "…"))
        if bare and bare[0].isupper() and len(bare) > 1 and not starts_sentence and not bare.isdigit():
            run.append(bare)
            if tok.endswith((",", ";", ":")) or len(run) == 4:
                break
        elif run:
            break
    return " ".join(run) or None


_CONNECTORS = {"năm", "vào", "từ", "đến", "tới", "trong", "khi", "lúc", "ngày", "tháng", "vào", "là"}


def date_context(narration: str, start: int, end: int) -> str | None:
    """The few words that say what happened at a year: the clause after it, else the clause before it
    (minus dangling 'từ năm' connectors). Cut from the narration itself, never written."""
    rest = re.split(r"[;:.!?…]", narration[end:], maxsplit=1)[0]  # to the end of the sentence
    for clause in rest.split(","):  # first clause with real content ('1204, trong cuộc Thập tự chinh' skips the empty one)
        words = clause.split()
        if len(words) >= 2:
            return " ".join(words[:7])
    before = re.split(r"[,;:.!?…]", narration[:start])[-1].split()
    while before and before[-1].lower().strip("()") in _CONNECTORS:
        before.pop()
    return " ".join(before[-7:]) or None


def derive_texts(preset: str, narration: str, policy: StoryboardPolicy | None = None) -> list[dict]:
    """-> [{"text", "role", "anchor"}] where `anchor` is the narration words that should be
    spoken when the text appears (used to cue it). Only text found in the narration is used."""
    policy = policy or StoryboardPolicy()
    sents = _sentences(narration)
    out: list[dict] = []
    if preset == "TimelineBuild":
        seen = set()
        for m in _YEAR.finditer(narration):
            y = m.group(1)
            if y in seen or _UNIT_AFTER_YEAR.match(narration[m.end():]) or not (100 <= int(y) <= 2100):
                continue
            seen.add(y)
            out.append({"text": y, "role": "date", "anchor": y, "sub": date_context(narration, m.start(), m.end())})
            if len(out) == 5:
                break
    elif preset == "BigNumber":
        unit_alt = policy.big_number_pattern.split("(?:", 1)[1].rsplit(")", 1)[0]  # the unit alternatives
        rng = re.search(rf"(\d[\d.,]*\d)\s*(?:đến|tới|-|–)\s*(\d[\d.,]*\d)\s*({unit_alt})", narration, re.I)
        m = re.search(policy.big_number_pattern, narration, re.I)
        if rng:  # 'từ 50.000 đến 80.000 binh sĩ' must not collapse to just '80.000'
            num, unit, end = f"{rng.group(1)}–{rng.group(2)}", rng.group(3), rng.end()
        elif m:
            raw = m.group(0)
            num = re.match(r"\d[\d.,]*", raw).group(0).rstrip(".,")
            unit = raw[len(num):].strip()
            end = m.end()
        else:  # a grouped (80.000) or long (12000) number with whatever noun follows it
            g = re.search(r"\d{1,3}(?:[.,]\d{3})+|\d{5,}", narration)
            num, unit, end = (g.group(0), "", g.end()) if g else ("", "", 0)
        if num:
            out.append({"text": num, "role": "number", "anchor": num})
            n_tail = 1 if unit.lower() in _MAGNITUDE else 0 if unit else 2  # 'triệu' needs its noun; 'người' stands alone
            tail = narration[end:].split()[:n_tail]
            label = " ".join(([unit] if unit else []) + tail).strip(" ,.;")
            if label:
                out.append({"text": label, "role": "label", "anchor": (unit or (tail[0] if tail else num))})
    elif preset == "HeadlineImpact":
        first = re.split(r"[,;:.!?…]", narration.strip())[0]
        out.append({"text": " ".join(first.split()[:8]), "role": "headline", "anchor": first.split()[0] if first.split() else ""})
    elif preset == "EvidenceBoard":
        limit = 150 if len(sents) == 1 else 100 if len(sents) == 2 else 80  # one card has room for a whole sentence
        for s in sents[:4]:
            out.append({"text": _clip(s, limit), "role": "caption", "anchor": s.split()[0]})
    elif preset == "NewspaperStack":
        for s in sents[:3]:
            out.append({"text": _clip(s, 62), "role": "headline", "anchor": s.split()[0]})
    elif preset == "SplitComparison":
        for s in sents[:2]:
            out.append({"text": _clip(s, 50), "role": "label", "anchor": s.split()[0]})
    elif preset in ("MapZoom", "ArchivalPortrait"):
        name = proper_noun(narration)
        if name:
            out.append({"text": name, "role": "label" if preset == "MapZoom" else "headline", "anchor": name.split()[0]})
    return [o for o in out if o["text"]]


def cue_frame(anchor: str, words: list[list], scene_start_sec: float, fps: int, default_index: int) -> int:
    """Frame (relative to the scene) at which `anchor`'s first word is spoken; falls back
    to a fixed stagger when that word is not in the timeline."""
    key = fold(anchor.split()[0]) if anchor.strip() else ""
    if key:
        for w in words:
            if fold(w[0]) == key:
                return max(0, round((w[1] - scene_start_sec) * fps))
    return default_index * STAGGER


def claim_status_for(claim_ids: list[int], statuses: dict[int, str]) -> str | None:
    have = [statuses[c] for c in claim_ids if c in statuses]
    if not have:
        return None
    if "disputed" in have:
        return "disputed"
    return "verified" if all(s == "verified" for s in have) else "unverified"


def credit_text(origin: str, license_: str | None, attribution: str | None, language: str = "vi") -> str | None:
    """On-screen credit an image needs: AI illustrations are labelled, attribution-licensed images credit
    their author, public-domain / own images need none."""
    en = language.lower().startswith("en")
    if origin == "ai_manual":
        return "AI illustration" if en else "Minh họa AI"
    if origin != "archival":
        return None
    lic = (license_ or "").strip()
    low = lic.lower()
    if not lic or low.startswith("public domain") or "cc0" in low or low == "pd":
        return None
    artist = re.sub(r"\s*[—-]\s*Wikimedia Commons\s*$", "", attribution or "").strip()
    return f"{'Image' if en else 'Ảnh'}: {artist} · {lic}" if artist else lic


# -- manifest ---------------------------------------------------------------------------------------
def remotion_source_hash() -> str:
    h = hashlib.sha256()
    files = sorted((REMOTION_DIR / "src").rglob("*.ts*")) + [REMOTION_DIR / "package.json"]
    for f in files:
        if f.is_file():
            h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:16]


def build_manifest(db: Session, root: Path, project_id: int, params: RenderParams) -> tuple[dict, dict[str, Path], str]:
    """-> (manifest, {public-relative path: source file}, input hash)."""
    narr = NarrationService(db, root)
    segments = narr.list(project_id)
    project = db.get(DocumentaryProject, project_id)
    language = project.language if project else "vi"
    timings = list(
        db.scalars(select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id).order_by(DocumentarySceneTiming.order_index))
    )
    if not timings or not segments:
        raise ValidationError("Chưa có timeline — hãy căn chỉnh và dựng timeline ở bước Giọng đọc trước.")
    scenes = {s.scene_key: s for s in db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == project_id))}
    assets = {a.id: a for a in db.scalars(select(DocumentaryAsset).where(DocumentaryAsset.project_id == project_id))}
    statuses = {c.id: c.status for c in db.scalars(select(DocumentaryClaim).where(DocumentaryClaim.project_id == project_id))}
    subs = list(
        db.scalars(select(DocumentarySubtitle).where(DocumentarySubtitle.project_id == project_id).order_by(DocumentarySubtitle.order_index))
    )

    total_sec = segments[-1].master_end or timings[-1].end
    total_frames = max(1, math.ceil(total_sec * FPS))
    bounds = [round(t.start * FPS) for t in timings] + [total_frames]
    public: dict[str, Path] = {}
    scene_rows = []
    for i, t in enumerate(timings):
        sc = scenes.get(t.scene_key)
        if sc is None:
            raise ValidationError(f"Cảnh {t.scene_key} có timing nhưng không còn trong storyboard — hãy dựng lại timeline.")
        start = bounds[i]
        dur = max(1, bounds[i + 1] - start)
        asset = assets.get(sc.asset_id) if sc.asset_id else None
        image, aspect = None, None
        if asset is not None and asset_state(sc, asset) == "approved":
            rel = f"images/{asset.content_hash[:16]}{Path(asset.path).suffix.lower()}"
            public[rel] = Path(asset.path)
            image = rel
            aspect = round(asset.width / asset.height, 4) if asset.width and asset.height else None
        user_texts = [{"text": x["text"], "role": x["role"], "anchor": x["text"]} for x in (sc.on_screen_text or [])]
        texts = user_texts or derive_texts(sc.visual_preset, sc.narration_text)
        preset = sc.visual_preset if sc.visual_preset in PRESETS else "PhotoKenBurns"
        if image is not None and preset in ("PhotoKenBurns", "ArchivalPortrait"):
            role = "caption" if preset == "PhotoKenBurns" else "label"
            if not any(x["role"] in ("caption", "label") for x in texts):  # never duplicate what the user typed
                credit = credit_text(asset.origin, asset.license, asset.attribution, language)
                if credit:
                    texts = texts + [{"text": credit, "role": role, "anchor": ""}]
        if not texts and image is None and preset in DATA_PRESETS:
            # A timeline with no years / a big number with no number would be an empty frame:
            # show the narration's own opening phrase instead.
            preset, texts = "HeadlineImpact", derive_texts("HeadlineImpact", sc.narration_text)
        rows = [
            {"text": x["text"], "role": x["role"], "sub": x.get("sub"), "cueFrame": min(dur - 1, cue_frame(x["anchor"], t.words, t.start, FPS, k))}
            for k, x in enumerate(texts)
        ]
        scene_rows.append(
            {
                "key": sc.scene_key, "preset": preset,
                "startFrame": start, "durationFrames": dur, "imageSrc": image, "imageAspect": aspect, "texts": rows,
                "claimStatus": claim_status_for(sc.claim_ids or [], statuses),
            }
        )
    manifest = {
        "theme": params.theme, "fps": FPS, "width": WIDTH, "height": HEIGHT,  # layout is in 1920x1080 units; previews shrink with --scale
        "durationInFrames": total_frames, "fadeFrames": FADE_FRAMES, "grayscale": params.grayscale,
        "burnSubtitles": params.burn_subtitles, "scenes": scene_rows,
        "subtitles": [
            {"startFrame": round(s.start * FPS), "endFrame": max(round(s.start * FPS) + 1, round(s.end * FPS)), "text": s.text}
            for s in subs
        ],
    }
    music_sha = None
    if params.music_path:
        from app.modules.documentary.assets import sha256_file

        music_sha = sha256_file(Path(params.music_path))  # a different track (or an edit) is a different video
    digest_src = json.dumps(
        {"m": manifest, "audio": narr.master_digest(segments), "remotion": remotion_source_hash(), "pipeline": PIPELINE_VERSION,
         "music": [music_sha, params.music_db] if music_sha else None,
         "normalize": params.normalize_audio, "seconds": params.seconds, "scale": params.scale},
        sort_keys=True, ensure_ascii=False,
    )
    return manifest, public, hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:16]


# -- preflight -------------------------------------------------------------------------------------------
def preflight(db: Session, root: Path, project_id: int, tools_ok: dict[str, bool]) -> list[ReviewIssue]:
    """Blocking problems that would make a render wrong or impossible, by scene ID."""
    issues: list[ReviewIssue] = []
    for tool, ok in tools_ok.items():
        if not ok:
            issues.append(ReviewIssue(code=f"missing_{tool}", message=f"Không tìm thấy {tool} — cần cài để render."))
    narr = NarrationService(db, root)
    base = narr.review(project_id)
    issues += base
    if base:
        return issues
    timings = {t.scene_key: t for t in db.scalars(select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id))}
    segments = narr.list(project_id)
    digest = narr.master_digest(segments)
    scenes = list(db.scalars(select(DocumentaryScene).where(DocumentaryScene.project_id == project_id).order_by(DocumentaryScene.order_index)))
    assets = {a.id: a for a in db.scalars(select(DocumentaryAsset).where(DocumentaryAsset.project_id == project_id))}
    for s in scenes:
        t = timings.get(s.scene_key)
        if t is None:
            issues.append(ReviewIssue(code="scene_no_timing", message=f"Cảnh {s.scene_key}: chưa có timing."))
        elif t.master_hash != digest:
            issues.append(ReviewIssue(code="timing_stale", message=f"Cảnh {s.scene_key}: timing cũ so với audio — dựng lại timeline."))
        if s.visual_preset not in PRESETS:
            issues.append(ReviewIssue(code="unknown_preset", message=f"Cảnh {s.scene_key}: preset '{s.visual_preset}' không tồn tại."))
        state = asset_state(s, assets.get(s.asset_id) if s.asset_id else None)
        if state not in ("programmatic", "approved"):
            issues.append(ReviewIssue(code=f"asset_{state}", message=f"Cảnh {s.scene_key}: ảnh chưa dùng được ({state})."))
    return issues
