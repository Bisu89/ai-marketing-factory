"""Manhua recap tool -- one comic chapter (page images) -> a finished recap Short.

Usage (backend running, with the backend venv's python):
    python recap.py fetch  <chapter_url> <chapter_dir> [--count N]
                                                          # download a chapter's page images (manhuavn2.com,
                                                          # cotruyenday.com, zettruyen*.com);
                                                          # --count N = this chapter and the next N-1
    python recap.py script <chapter_dir> --mode premise   # multi-chapter "sell the series" recap
    python recap.py cut    <chapter_dir>                  # split pages into panels -> <chapter_dir>/_recap/panels/
    python recap.py script <chapter_dir> [--seconds 50] [--notes "..."]
                                                          # AI reads the panels, writes _recap/script.json
    python recap.py sheets <chapter_dir>                  # numbered reading sheets (6 panels each) so a
                                                          # person / Claude can read the chapter and write
                                                          # script.json by hand -- no OpenAI cost
    python recap.py build  <chapter_dir> [--script FILE] [--name "..."] [--no-render] [--commentary-voice VOICE|same]
                                         [--captions color|yellow]
                                                          # register panels, create the project, start the render

<chapter_dir> holds the chapter's page images (jpg/png/webp) in reading order by
filename. Between steps you can delete bad panels from _recap/panels/ (then re-run
`script`) or hand-edit _recap/script.json (title / narration / which panel) before
`build`. The project uses the built-in "manhua_recap_vi" template.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

API = os.environ.get("MANHUA_API", "http://127.0.0.1:8000/api/v1")  # override to target another backend
TEMPLATE_ID = "manhua_recap_vi"
# Host-commentary beats are read by a second voice (female) so viewers hear
# the channel's own take as distinct from the recap (male, the template's).
COMMENTARY_VOICE = "vi-VN-HoaiMyNeural"
PAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
# Same pace the backend's script writer targets (measured: NamMinh @1.6 ~ 5.1 syllables/s).
SYLLABLES_PER_SECOND = 5.1

# -- fetching -------------------------------------------------------------------
# manhuavn2.com chapter pages list their page images as <img class="lazy"
# data-original="...">; the same markup is used for the sidebar's cover
# thumbnails, which all live under /Pictures/Truyen/. VIP chapters are marked
# "isAccessibleForFree": false and carry no page images.
# cotruyenday.com (…/truyen-tranh/<slug>/chapter-N, no .html) serves page
# images from images.jino277.work/prod/chapters/…; the URLs can contain
# spaces, so they are percent-encoded before download. Chapters past the
# free ones (ch.11+ on Dai Quan Gia, 2026-09-28) come back with no images.
# zettruyen*.com (…/truyen-tranh/<slug>/chuong-N) serves pages from
# cdnN.zetimage.com/<slug>/<N>/<i>.jpg; that CDN answers 403 without a
# Referer from the site (hotlink protection), and /thumb/ holds sidebar covers.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
COVER_PATH = "/Pictures/Truyen/"


def _get(url: str, timeout: int = 60, referer: str | None = None) -> bytes:
    url = urllib.parse.quote(url, safe=":/%?=&")
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _chapter_page_urls(url: str) -> list[str]:
    html = _get(url).decode("utf-8", errors="replace")
    if re.search(r'"isAccessibleForFree"\s*:\s*false', html):
        sys.exit(f"{url} is VIP/locked on the site -- pick free chapters.")
    if "cotruyenday.com" in url:
        urls = list(dict.fromkeys(re.findall(r'["\'](https?://images\.jino277\.work/prod/chapters/[^"\']+)', html)))
    elif "zettruyen" in url:
        urls = [u for u in dict.fromkeys(re.findall(r'(https?://cdn\d*\.zetimage\.com/[^"\'\s\\]+)', html))
                if "/thumb/" not in u]
    else:
        urls = [u for u in re.findall(r'data-original="([^"]+)"', html) if COVER_PATH not in u]
    if not urls:
        sys.exit(f"No page images found on {url} -- a chapter URL? (cotruyenday: only free / logged-out chapters work)")
    return urls


def cmd_fetch(url: str, chapter: Path, count: int = 1) -> None:
    """count > 1: also fetch the next chapters by bumping `-chapter-N` in the URL.
    Pages are named c<chapter>_<page>.jpg so `cut` stacks them in reading order."""
    match = re.search(r"(?:chapter|chuong)-(\d+)(\.html)?/?$", url)
    if count > 1 and not match:
        sys.exit("--count needs a URL ending in chapter-N / chuong-N (or -chapter-N.html)")
    referer = "{0.scheme}://{0.netloc}/".format(urllib.parse.urlparse(url))
    chapter.mkdir(parents=True, exist_ok=True)
    total = 0
    for k in range(count):
        n = int(match.group(1)) + k if match else None
        chapter_url = url if k == 0 else url[:match.start(1)] + str(n) + url[match.end(1):]
        urls = _chapter_page_urls(chapter_url)
        prefix = f"c{n:03d}_" if count > 1 else ""
        for i, image_url in enumerate(urls, 1):
            (chapter / f"{prefix}{i:03d}.jpg").write_bytes(_get(image_url, referer=referer))
            print(f"\rchapter {n or ''}: {i}/{len(urls)}", end="", flush=True)
        print()
        total += len(urls)
    print(f"{total} page(s) -> {chapter}. Next: `cut`.")


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


def _stack(pages: list[Path]) -> tuple[np.ndarray, list[int]]:
    """The vertical strip, plus each page's starting row in it."""
    parts, starts, row = [], [], 0
    for page in pages:
        with Image.open(page) as img:
            img = img.convert("RGB")
            if img.width != STRIP_WIDTH:
                img = img.resize((STRIP_WIDTH, round(img.height * STRIP_WIDTH / img.width)), Image.LANCZOS)
            parts.append(np.asarray(img))
            starts.append(row)
            row += parts[-1].shape[0]
    return np.concatenate(parts, axis=0), starts


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
    strip, page_starts = _stack(pages)
    out = chapter / "_recap" / "panels"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("p*.jpg"):
        old.unlink()

    kept = 0
    pieces = [piece for top, bottom in _segments(_flat_rows(strip)) for piece in _split_tall(strip, top, bottom)]
    # 3-digit names (p001) as before; 4 only for 1000+ piece runs (multi-chapter
    # long videos), so names still sort in reading order.
    width = 3 if len(pieces) < 1000 else 4
    # Which source page each panel starts on -- with `fetch --count` pages are
    # named c<chapter>_<page>, so this is also the panel's chapter.
    panel_pages: dict[str, str] = {}
    for top, bottom in pieces:
        if bottom - top < PANEL_MIN_HEIGHT:
            continue
        panel = _trim_columns(strip[top:bottom])
        if panel.shape[1] < PANEL_MIN_HEIGHT or _ink_ratio(panel) < PANEL_MIN_INK:
            continue
        kept += 1
        name = f"p{kept:0{width}d}.jpg"
        Image.fromarray(panel).save(out / name, quality=92)
        page_index = max(i for i, start in enumerate(page_starts) if start <= top)
        panel_pages[name] = pages[page_index].name

    if kept == 0:
        sys.exit("No panels found -- are these really comic pages with gutters between panels?")
    (out.parent / "panel_pages.json").write_text(json.dumps(panel_pages, indent=0), encoding="utf-8")
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


# Reading sheets: big enough to read speech bubbles, 6 panels per image, each
# labelled with its file name -- the unit a hand-written script.json refers to.
SHEET_CELL = (620, 900)
SHEET_COLS, SHEET_ROWS = 3, 2


def cmd_sheets(chapter: Path) -> None:
    from PIL import ImageDraw, ImageFont
    panels = _panel_files(chapter)
    map_file = chapter / "_recap" / "panel_pages.json"
    page_of = json.loads(map_file.read_text(encoding="utf-8")) if map_file.exists() else {}
    out = chapter / "_recap" / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sheet_*.jpg"):
        old.unlink()
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    per = SHEET_COLS * SHEET_ROWS
    cw, ch = SHEET_CELL
    for n, start in enumerate(range(0, len(panels), per), 1):
        sheet = Image.new("RGB", (SHEET_COLS * cw, SHEET_ROWS * (ch + 50)), "white")
        draw = ImageDraw.Draw(sheet)
        for k, panel in enumerate(panels[start:start + per]):
            x, y = (k % SHEET_COLS) * cw, (k // SHEET_COLS) * (ch + 50)
            with Image.open(panel) as img:
                img = img.convert("RGB")
                img.thumbnail((cw - 10, ch - 10))
                sheet.paste(img, (x + (cw - img.width) // 2, y + 50))
            source = page_of.get(panel.name, "")
            label = f"{panel.name}  [{source.split('_')[0]}]" if "_" in source else panel.name
            draw.text((x + 10, y + 4), label, fill="red", font=font)
        sheet.save(out / f"sheet_{n:02d}.jpg", quality=88)
    print(f"{len(panels)} panels -> {n} sheet(s) in {out}")


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


# Must match the backend's MAX_PANELS (endpoints/manhua_recap.py).
MAX_PANELS = 150


def cmd_script(chapter: Path, seconds: float, notes: str | None, commentary: bool, mode: str = "chapter") -> None:
    panels = _panel_files(chapter)
    if len(panels) > MAX_PANELS:
        # A premise run over several chapters: keep an even spread so every
        # chapter is still represented.
        step = len(panels) / MAX_PANELS
        panels = [panels[int(i * step)] for i in range(MAX_PANELS)]
        print(f"{len(_panel_files(chapter))} panels > {MAX_PANELS}: sending an even sample of {MAX_PANELS}.")
    print(f"Sending {len(panels)} panels to the AI ({mode} mode, this can take a minute)...")
    result = call("POST", "/manhua-recap/script", {
        "panel_paths": [str(p.resolve()) for p in panels], "target_duration": seconds,
        "language": "vi", "notes": notes, "commentary": commentary, "mode": mode,
    }, timeout=600)
    script = {
        "title": result["title"],
        "beats": [{"panel": panels[b["panel"] - 1].name, "type": b["type"], "kind": b.get("kind", "recap"),
                   "narration": b["narration"]} for b in result["beats"]],
    }
    path = chapter / "_recap" / "script.json"
    path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    syllables = sum(len(b["narration"].split()) for b in script["beats"])
    print(f"{script['title']}\n{len(script['beats'])} beats, ~{syllables / SYLLABLES_PER_SECOND:.0f}s -> {path}")
    for b in script["beats"]:
        tag = "BÌNH LUẬN" if b["kind"] == "commentary" else "kể"
        print(f"  [{b['panel']}] ({tag}) {b['narration']}")
    print("Edit script.json if needed (make the commentary sound like YOU), then run `build`.")


CAPTION_STYLES = {"color": "word_pop", "yellow": "word_pop_yellow"}
# Narration pace per template (syllables/s) -- only used for the pre-voice
# duration estimate; the Voice stage sets the real beat timings.
TEMPLATE_PACE = {"manhua_recap_vi": 5.1, "manhua_recap_long_vi": 4.2}


def cmd_build(
    chapter: Path, name: str | None, render: bool, commentary_voice: str | None, captions: str | None = None,
    script_path: Path | None = None,
) -> None:
    # --script lets the script live somewhere version-controlled (manhua-series/)
    # while the heavy page/panel images stay local in the chapter dir.
    script_path = script_path or chapter / "_recap" / "script.json"
    if not script_path.exists():
        sys.exit(f"No script at {script_path} -- run `script` (or write one by hand) first.")
    script = json.loads(script_path.read_text(encoding="utf-8"))
    # "template" in script.json picks Short (default) vs long-form 16:9.
    template_id = script.get("template", TEMPLATE_ID)
    pace = TEMPLATE_PACE.get(template_id, SYLLABLES_PER_SECOND)
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
            "id": f"b{i}", "order": i,
            "type": "HOOK" if i == 1 else "ENDING" if i == len(script["beats"]) else b.get("type", "BUILD"),
            "narration": text, "duration": round(max(1.2, len(text.split()) / pace + 0.15), 2),
            "visual_hint": path.stem, "asset_id": asset["id"],
            "voice_id": commentary_voice if b.get("kind") == "commentary" else None,
        })

    name = name or script["title"]
    text = " ".join(b["narration"] for b in beats)
    pid = call("POST", "/projects", {"name": name, "template_id": template_id, "script_text": text,
                                     "content_language": "vi", "visual_generation_mode": "library"})["id"]
    cfg = call("GET", f"/projects/{pid}")["config"]
    cfg["content"]["target_duration"] = float(round(sum(b["duration"] for b in beats)))
    if captions:  # otherwise keep the template's own caption style
        cfg["captions"]["preset"] = CAPTION_STYLES[captions]
    call("PUT", f"/projects/{pid}/beat-plan", {"project_name": name, "script_text": text, "script_locked": True,
                                                "beats": beats, "config": cfg})
    # Hand-written metadata from script.json (the manhua templates have AI
    # metadata off). App limits: title 70 chars, description 500.
    overrides = {"title": script["title"][:70]}
    if script.get("description"):
        overrides["description"] = script["description"][:500]
    if script.get("hashtags"):
        overrides["hashtags"] = script["hashtags"]
    call("PUT", f"/projects/{pid}/package-overrides", overrides)
    if not render:
        print(f"project {pid} ({name}) created -- open it in the app to render.")
        return
    run = call("POST", f"/projects/{pid}/factory-run")
    print(f"project {pid} ({name}), factory run {run['id']} {run['status']}")


def cmd_timestamps(project_id: int, script_path: Path) -> None:
    """YouTube chapter timestamps for a rendered long video: every beat in
    script.json carrying a "section" title starts a chapter, at the real
    start time the Voice stage gave that beat."""
    script = json.loads(script_path.read_text(encoding="utf-8"))
    beats = sorted(call("GET", f"/projects/{project_id}")["beats"], key=lambda b: b["order"])
    if len(beats) != len(script["beats"]):
        sys.exit(f"project {project_id} has {len(beats)} beats, script has {len(script['beats'])} -- wrong pair?")
    for sb, pb in zip(script["beats"], beats):
        if sb.get("section"):
            start = int(pb.get("start") or 0)
            print(f"{start // 60}:{start % 60:02d} {sb['section']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("url")
    fetch.add_argument("chapter", type=Path)
    fetch.add_argument("--count", type=int, default=1, help="fetch this chapter and the next COUNT-1")
    ts = sub.add_parser("timestamps")
    ts.add_argument("project_id", type=int)
    ts.add_argument("--script", type=Path, required=True)
    for cmd in ("cut", "sheets", "script", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("chapter", type=Path)
        if cmd == "script":
            p.add_argument("--seconds", type=float, default=50.0)
            p.add_argument("--notes", default=None, help="context the panels can't give (names, who's who)")
            p.add_argument("--no-commentary", action="store_true",
                           help="plain recap, no host commentary (higher reused-content risk on YouTube)")
            p.add_argument("--mode", choices=("chapter", "premise"), default="chapter",
                           help="chapter = recap one chapter; premise = sell the series from its first chapters")
        if cmd == "build":
            p.add_argument("--script", type=Path, default=None,
                           help="script.json to build from (default <chapter_dir>/_recap/script.json)")
            p.add_argument("--name", default=None)
            p.add_argument("--no-render", action="store_true")
            p.add_argument("--commentary-voice", default=COMMENTARY_VOICE,
                           help=f"edge-tts voice for commentary beats (default {COMMENTARY_VOICE}; 'same' = narrator's)")
            p.add_argument("--captions", choices=tuple(CAPTION_STYLES), default=None,
                           help="Shorts only: color = each word a different colour; yellow = every word yellow")
    args = parser.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(args.url, args.chapter.resolve(), args.count)
        return
    if args.cmd == "timestamps":
        cmd_timestamps(args.project_id, args.script.resolve())
        return
    chapter = args.chapter.resolve()
    if not chapter.is_dir():
        sys.exit(f"Not a folder: {chapter}")
    if args.cmd == "cut":
        cmd_cut(chapter)
    elif args.cmd == "sheets":
        cmd_sheets(chapter)
    elif args.cmd == "script":
        cmd_script(chapter, args.seconds, args.notes, not args.no_commentary, args.mode)
    else:
        cmd_build(chapter, args.name, not args.no_render,
                  None if args.commentary_voice == "same" else args.commentary_voice, args.captions,
                  args.script.resolve() if args.script else None)


if __name__ == "__main__":
    main()
