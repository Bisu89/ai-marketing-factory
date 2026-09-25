"""Manhua recap tool -- one comic chapter (page images) -> a finished recap Short.

Usage (backend running, with the backend venv's python):
    python recap.py fetch  <chapter_url> <chapter_dir>    # download a chapter's page images (manhuavn2.com)
    python recap.py cut    <chapter_dir>                  # split pages into panels -> <chapter_dir>/_recap/panels/
    python recap.py script <chapter_dir> [--seconds 50] [--notes "..."]
                                                          # AI reads the panels, writes _recap/script.json
    python recap.py build  <chapter_dir> [--name "..."] [--no-render]
                                                          # register panels, create the project, start the render

<chapter_dir> holds the chapter's page images (jpg/png/webp) in reading order by
filename. Between steps you can delete bad panels from _recap/panels/ (then re-run
`script`) or hand-edit _recap/script.json (title / narration / which panel) before
`build`. The project uses the built-in "manhua_recap_vi" template.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

API = "http://127.0.0.1:8000/api/v1"
TEMPLATE_ID = "manhua_recap_vi"
PAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
# Same pace the backend's script writer targets (reference sample: ~335 syllables/min).
SYLLABLES_PER_SECOND = 5.5

# -- fetching -------------------------------------------------------------------
# manhuavn2.com chapter pages list their page images as <img class="lazy"
# data-original="...">; the same markup is used for the sidebar's cover
# thumbnails, which all live under /Pictures/Truyen/. VIP chapters are marked
# "isAccessibleForFree": false and carry no page images.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
COVER_PATH = "/Pictures/Truyen/"


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cmd_fetch(url: str, chapter: Path) -> None:
    html = _get(url).decode("utf-8", errors="replace")
    if re.search(r'"isAccessibleForFree"\s*:\s*false', html):
        sys.exit("This chapter is VIP/locked on the site -- pick a free chapter.")
    urls = [u for u in re.findall(r'data-original="([^"]+)"', html) if COVER_PATH not in u]
    if not urls:
        sys.exit("No page images found on that page -- is it a chapter URL (…/doc-truyen/…-chapter-N.html)?")
    chapter.mkdir(parents=True, exist_ok=True)
    for i, image_url in enumerate(urls, 1):
        (chapter / f"{i:03d}.jpg").write_bytes(_get(image_url))
        print(f"\r{i}/{len(urls)}", end="", flush=True)
    print(f"\n{len(urls)} page(s) -> {chapter}. Next: `cut`.")


# -- panel cutting ------------------------------------------------------------
# Web manhua/webtoon chapters are tall vertical strips cut into arbitrary page
# images, with panels separated by horizontal bands of flat colour (white,
# black or a flat tint). So: stack every page into one strip, find rows that
# are (almost) a single flat colour, and cut wherever such rows run for at
# least GUTTER_MIN_ROWS. Side-by-side panels in one row stay together -- fine
# for this format, where that's rare.
ROW_FLAT_STD = 6.0       # a row whose pixel std-dev is below this is "flat"
GUTTER_MIN_ROWS = 6      # this many flat rows in a row = a gutter
PANEL_MIN_HEIGHT = 150   # anything shorter is a divider/text scrap, dropped
PANEL_MIN_INK = 0.04     # fraction of non-flat pixels a real panel needs
STRIP_WIDTH = 900        # every page is resized to this width before stacking
# Panels that bleed into each other (speech bubbles over the gutter, full-bleed
# art) come out as one very tall segment -- and a 9:16 cover-crop would only
# ever show its middle. Anything taller than this many widths is split again
# at its emptiest rows (most near-white/near-black pixels).
MAX_PANEL_ASPECT = 2.0
MIN_SPLIT_PIECE = 0.7    # a split piece is at least this many widths tall


def _natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def _pages(chapter: Path) -> list[Path]:
    pages = sorted((p for p in chapter.iterdir() if p.suffix.lower() in PAGE_EXTS), key=_natural_key)
    if not pages:
        sys.exit(f"No page images (jpg/png/webp) found in {chapter}")
    return pages


def _stack(pages: list[Path]) -> np.ndarray:
    parts = []
    for page in pages:
        with Image.open(page) as img:
            img = img.convert("RGB")
            if img.width != STRIP_WIDTH:
                img = img.resize((STRIP_WIDTH, round(img.height * STRIP_WIDTH / img.width)), Image.LANCZOS)
            parts.append(np.asarray(img))
    return np.concatenate(parts, axis=0)


def _flat_rows(strip: np.ndarray) -> np.ndarray:
    gray = strip.mean(axis=2)
    # Ignore a 3% margin each side -- scan artefacts / page borders live there.
    margin = max(1, strip.shape[1] // 33)
    return gray[:, margin:-margin].std(axis=1) < ROW_FLAT_STD


def _segments(flat: np.ndarray) -> list[tuple[int, int]]:
    """Content runs between gutters, as (top, bottom) row indices."""
    segments, start, gap = [], None, 0
    for y, is_flat in enumerate(flat):
        if is_flat:
            gap += 1
            if start is not None and gap >= GUTTER_MIN_ROWS:
                segments.append((start, y - gap + 1))
                start = None
        else:
            if start is None:
                start = y
            gap = 0
    if start is not None:
        segments.append((start, len(flat)))
    return segments


def _split_tall(strip: np.ndarray, top: int, bottom: int) -> list[tuple[int, int]]:
    """Recursively cut an over-tall segment at its emptiest row band."""
    width = strip.shape[1]
    if (bottom - top) <= MAX_PANEL_ASPECT * width:
        return [(top, bottom)]
    gray = strip[top:bottom].mean(axis=2)
    empty = ((gray > 235) | (gray < 20)).mean(axis=1)
    empty = np.convolve(empty, np.ones(9) / 9, mode="same")  # prefer a band, not one lucky row
    lo, hi = int(MIN_SPLIT_PIECE * width), (bottom - top) - int(MIN_SPLIT_PIECE * width)
    cut = top + lo + int(np.argmax(empty[lo:hi]))
    return _split_tall(strip, top, cut) + _split_tall(strip, cut, bottom)


def _trim_columns(panel: np.ndarray) -> np.ndarray:
    cols = panel.mean(axis=2).std(axis=0) >= ROW_FLAT_STD
    idx = np.flatnonzero(cols)
    return panel if idx.size == 0 else panel[:, idx[0]:idx[-1] + 1]


def _ink_ratio(panel: np.ndarray) -> float:
    gray = panel.mean(axis=2)
    background = np.median(gray)
    return float((np.abs(gray - background) > 25).mean())


def cmd_cut(chapter: Path) -> None:
    pages = _pages(chapter)
    strip = _stack(pages)
    out = chapter / "_recap" / "panels"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("p*.jpg"):
        old.unlink()

    kept = 0
    pieces = [piece for top, bottom in _segments(_flat_rows(strip)) for piece in _split_tall(strip, top, bottom)]
    for top, bottom in pieces:
        if bottom - top < PANEL_MIN_HEIGHT:
            continue
        panel = _trim_columns(strip[top:bottom])
        if panel.shape[1] < PANEL_MIN_HEIGHT or _ink_ratio(panel) < PANEL_MIN_INK:
            continue
        kept += 1
        Image.fromarray(panel).save(out / f"p{kept:03d}.jpg", quality=92)

    if kept == 0:
        sys.exit("No panels found -- are these really comic pages with gutters between panels?")
    _contact_sheet(out)
    print(f"{len(pages)} page(s) -> {kept} panel(s) in {out}")
    print(f"Check {out.parent / 'panels_preview.jpg'}; delete any junk panel files, then run `script`.")


def _contact_sheet(panels_dir: Path, thumb_h: int = 260, per_row: int = 8) -> None:
    thumbs = []
    for p in sorted(panels_dir.glob("p*.jpg")):
        with Image.open(p) as img:
            img.thumbnail((thumb_h, thumb_h))
            thumbs.append((p.stem, img.copy()))
    rows = (len(thumbs) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (thumb_h + 10), rows * (thumb_h + 30)), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(thumbs):
        x, y = (i % per_row) * (thumb_h + 10), (i // per_row) * (thumb_h + 30)
        sheet.paste(img, (x + (thumb_h - img.width) // 2, y))
        draw.text((x + 4, y + thumb_h + 6), name, fill="black")
    sheet.save(panels_dir.parent / "panels_preview.jpg", quality=85)


# -- API ------------------------------------------------------------------------

def call(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}: {e.read().decode()[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"Backend not reachable at {API} ({e.reason}) -- start it first.")


def _panel_files(chapter: Path) -> list[Path]:
    panels = sorted((chapter / "_recap" / "panels").glob("p*.jpg"))
    if not panels:
        sys.exit("No panels yet -- run `cut` first.")
    return panels


def cmd_script(chapter: Path, seconds: float, notes: str | None) -> None:
    panels = _panel_files(chapter)
    print(f"Sending {len(panels)} panels to the AI (this can take a minute)...")
    result = call("POST", "/manhua-recap/script", {
        "panel_paths": [str(p.resolve()) for p in panels], "target_duration": seconds,
        "language": "vi", "notes": notes,
    }, timeout=600)
    script = {
        "title": result["title"],
        "beats": [{"panel": panels[b["panel"] - 1].name, "narration": b["narration"]} for b in result["beats"]],
    }
    path = chapter / "_recap" / "script.json"
    path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    syllables = sum(len(b["narration"].split()) for b in script["beats"])
    print(f"{script['title']}\n{len(script['beats'])} beats, ~{syllables / SYLLABLES_PER_SECOND:.0f}s -> {path}")
    for b in script["beats"]:
        print(f"  [{b['panel']}] {b['narration']}")
    print("Edit script.json if needed, then run `build`.")


def cmd_build(chapter: Path, name: str | None, render: bool) -> None:
    script_path = chapter / "_recap" / "script.json"
    if not script_path.exists():
        sys.exit("No script yet -- run `script` first.")
    script = json.loads(script_path.read_text(encoding="utf-8"))
    panels_dir = chapter / "_recap" / "panels"
    tag = re.sub(r"[^a-z0-9]+", "_", chapter.name.lower()).strip("_") or "chapter"

    known = {str(Path(a["path"])).lower(): a for a in call("GET", "/assets?q=manhua_recap&asset_type=image")}
    beats = []
    for i, b in enumerate(script["beats"], 1):
        path = (panels_dir / b["panel"]).resolve()
        if not path.exists():
            sys.exit(f"Beat {i}: panel file {b['panel']} not found in {panels_dir}")
        asset = known.get(str(path).lower())
        if asset is None:
            with Image.open(path) as img:
                w, h = img.size
            asset = call("POST", "/assets", {"filename": f"{tag}_{path.name}", "path": str(path), "type": "image",
                                             "width": w, "height": h, "tags": ["manhua_recap", tag]})
        text = b["narration"].strip()
        beats.append({
            "id": f"b{i}", "order": i, "type": "HOOK" if i == 1 else "ENDING" if i == len(script["beats"]) else "BUILD",
            "narration": text, "duration": round(max(1.2, len(text.split()) / SYLLABLES_PER_SECOND + 0.15), 2),
            "visual_hint": path.stem, "asset_id": asset["id"],
        })

    name = name or script["title"]
    text = " ".join(b["narration"] for b in beats)
    pid = call("POST", "/projects", {"name": name, "template_id": TEMPLATE_ID, "script_text": text,
                                     "content_language": "vi", "visual_generation_mode": "library"})["id"]
    cfg = call("GET", f"/projects/{pid}")["config"]
    cfg["content"]["target_duration"] = float(round(sum(b["duration"] for b in beats)))
    call("PUT", f"/projects/{pid}/beat-plan", {"project_name": name, "script_text": text, "script_locked": True,
                                                "beats": beats, "config": cfg})
    call("PUT", f"/projects/{pid}/package-overrides", {"title": script["title"]})
    if not render:
        print(f"project {pid} ({name}) created -- open it in the app to render.")
        return
    run = call("POST", f"/projects/{pid}/factory-run")
    print(f"project {pid} ({name}), factory run {run['id']} {run['status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("url")
    fetch.add_argument("chapter", type=Path)
    for cmd in ("cut", "script", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("chapter", type=Path)
        if cmd == "script":
            p.add_argument("--seconds", type=float, default=50.0)
            p.add_argument("--notes", default=None, help="context the panels can't give (names, who's who)")
        if cmd == "build":
            p.add_argument("--name", default=None)
            p.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(args.url, args.chapter.resolve())
        return
    chapter = args.chapter.resolve()
    if not chapter.is_dir():
        sys.exit(f"Not a folder: {chapter}")
    if args.cmd == "cut":
        cmd_cut(chapter)
    elif args.cmd == "script":
        cmd_script(chapter, args.seconds, args.notes)
    else:
        cmd_build(chapter, args.name, not args.no_render)


if __name__ == "__main__":
    main()
