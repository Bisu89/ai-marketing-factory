"""Biblical Figures episode tool -- image pool reuse + ChatGPT prompt CSVs + app project build.

Usage (from anywhere, with the backend venv's python):
    python bf.py pool                     # rebuild _pool/pool.csv (what exists, who is in it, where it was used)
    python bf.py prompts 2                # validate ep2 spec, write CSVs of NEW images only + script + title file
    python bf.py build 2 long|short       # register new images, create the project in the app, start the render

An episode is described by  biblical_figures_ep<N>_spec.json  (see RULES.md for the format).
Each beat is one of  {"new": {"stem", "tags", "scene", "chars"}}  (a new image),
{"repeat": "<stem of a new image in this same video>"}  or  {"reuse": "<pool filename>"}.
    python bf.py aigen 2 long|short       # generate the new images with the app's image API (mini, low)
"""
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bf_style import CHAR, CHAR_NAMES, POOL_FLAGS, STYLE_MARKERS, STYLE_NAME, build_prompt

ROOT = Path(__file__).resolve().parent.parent
POOL_CSV = ROOT / "_pool" / "pool.csv"
API = "http://127.0.0.1:8000/api/v1"
CSV_HEADER = ["STT", "Ten file (filename.png)", "Tags (dan khi import)", "Prompt day du (copy nguyen vao ChatGPT)"]
POOL_HEADER = ["filename", "orientation", "style", "episode", "asset_id", "characters", "reuse", "used_in", "tags", "path"]
# Measured on Ep1 renders (en-GB-RyanNeural): long @0.95 = 1889 words / 760s, short @1.1 = 77 words / 25.3s.
WPM = {"long": 149, "short": 183}
HOOK_FRESH_BEATS = 3  # the first beats of a video should be brand-new images, never reused
MAX_USES = 3  # "repeat": one new image may cover at most this many beats of one video...
MIN_GAP = 3   # ...and never two beats closer than this
DESCRIPTION_LIMIT = 500  # app's own metadata limit (the full description goes in the .txt for YouTube)


# -- helpers ---------------------------------------------------------------

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code}: {e.read().decode()[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"Backend not reachable at {API} ({e.reason}) -- start it first.")


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_HEADER)
        w.writerows(rows)


def images_dir(ep, version):
    return ROOT / f"biblical_figures_ep{ep}_{version}_images"


def load_spec(ep):
    path = ROOT / f"biblical_figures_ep{ep}_spec.json"
    if not path.exists():
        sys.exit(f"Missing spec: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_pool():
    if not POOL_CSV.exists():
        sys.exit("No pool yet -- run: python bf.py pool")
    with open(POOL_CSV, encoding="utf-8-sig") as f:
        return {r["filename"]: r for r in csv.DictReader(f)}


def new_filename(ep, version, index, new):
    if new.get("file"):
        return new["file"]
    return f"ep{ep}_{index:03d}_{new['stem']}.png" if version == "long" else f"ep{ep}_short_{index:02d}_{new['stem']}.png"


def image_of(ep, version, beats, i):
    """Filename a beat shows: its own new image, a repeat of one, or a pool reuse."""
    beat = beats[i - 1]
    if "new" in beat:
        return new_filename(ep, version, i, beat["new"])
    if "repeat" in beat:
        for j, other in enumerate(beats, 1):
            if "new" in other and other["new"]["stem"] == beat["repeat"]:
                return new_filename(ep, version, j, other["new"])
        return None
    return beat["reuse"]


def library_images():
    assets = call("GET", "/assets?q=biblical_figures&asset_type=image")
    return {str(Path(a["path"])).lower(): a for a in assets if "biblical_figures" in a["tags"]}


# -- pool ------------------------------------------------------------------

def characters_in(prompt):
    """Series characters by their exact bible text (bf_style.CHAR); an episode-only
    character (spec "characters") falls back to the first word of its name."""
    names = {CHAR_NAMES[k] for k, bible in CHAR.items() if bible in prompt}
    for full in re.findall(r"recurring character ([A-Z][\w ]+?):", prompt):
        if not any(bible.startswith(f"recurring character {full}:") for bible in CHAR.values()):
            names.add(full.split()[0].lower())
    return names


def cmd_pool():
    lib = library_images()
    used = {}
    for spec_path in sorted(ROOT.glob("biblical_figures_ep*_spec.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        for version in ("long", "short"):
            for beat in spec.get(version, []):
                if "reuse" in beat:
                    used.setdefault(beat["reuse"], set()).add(spec["episode"])
    rows = []
    for csv_path in sorted(ROOT.glob("biblical_figures_ep*_*_scenes.csv")):
        m = re.match(r"biblical_figures_ep(\d+)_(long|short)_scenes\.csv", csv_path.name)
        if not m:
            continue
        ep, version = int(m.group(1)), m.group(2)
        with open(csv_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                fn = r["Ten file (filename.png)"]
                if fn.startswith("000_") or "_ref_" in fn or "_thumbnail_" in fn:
                    continue  # face-lock reference / YouTube thumbnail, never imported
                path = images_dir(ep, version) / fn
                asset = lib.get(str(path).lower())
                names = sorted(characters_in(r[CSV_HEADER[3]]))
                named = [n for n in names if n != "jesus"]  # back-view Jesus shots fit any Gospel-era episode
                reuse = POOL_FLAGS.get(fn) or ("with:" + "+".join(named) if named else "any")
                style = next((k for k, marker in STYLE_MARKERS.items() if marker in r[CSV_HEADER[3]]), "unknown")
                rows.append([fn, "16:9" if version == "long" else "9:16", style, ep, asset["id"] if asset else "",
                             "+".join(names), reuse, "+".join(str(e) for e in sorted(used.get(fn, set()) | {ep})),
                             r["Tags (dan khi import)"], str(path)])
    POOL_CSV.parent.mkdir(exist_ok=True)
    with open(POOL_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(POOL_HEADER)
        w.writerows(rows)
    missing = [r[0] for r in rows if not r[4]]
    current = [r for r in rows if r[2] == STYLE_NAME]
    print(f"pool: {len(rows)} images, {len(current)} in the current '{STYLE_NAME}' style "
          f"({sum(r[1] == '16:9' for r in current)} landscape, {sum(r[1] == '9:16' for r in current)} portrait, "
          f"{sum(r[6] == 'any' for r in current)} reusable in any episode) -> {POOL_CSV}")
    if missing:
        print(f"  not in app library yet (import happens at build): {len(missing)}")


# -- prompts ---------------------------------------------------------------

def validate(spec, pool):
    ep, cast = spec["episode"], {c.lower() for c in spec.get("cast", [])}
    errors, warnings, repeats = [], [], []
    for version in ("long", "short"):
        seen, uses = set(), {}
        orient = "16:9" if version == "long" else "9:16"
        for i, beat in enumerate(spec.get(version, []), 1):
            where = f"{version} beat {i}"
            if sum(k in beat for k in ("reuse", "new", "repeat")) != 1:
                errors.append(f"{where}: needs exactly one of 'new' / 'repeat' / 'reuse'")
                continue
            if "new" in beat:
                fn = new_filename(ep, version, i, beat["new"])
            elif "repeat" in beat:
                fn = image_of(ep, version, spec[version], i)
                if fn is None:
                    errors.append(f"{where}: repeat '{beat['repeat']}' is not a new image of this video")
                    continue
                if i <= HOOK_FRESH_BEATS:
                    errors.append(f"{where}: hook beats must show their own new image")
                uses.setdefault(fn, []).append(i)
                continue
            else:
                fn = beat["reuse"]
                row = pool.get(fn)
                if row is None:
                    errors.append(f"{where}: '{fn}' is not in the pool")
                    continue
                if row["style"] != STYLE_NAME:
                    errors.append(f"{where}: '{fn}' is in the old '{row['style']}' style, series is now '{STYLE_NAME}'")
                if row["orientation"] != orient:
                    errors.append(f"{where}: '{fn}' is {row['orientation']}, this version needs {orient}")
                rule = row["reuse"]
                if rule.startswith("avoid") and not beat.get("force"):
                    errors.append(f"{where}: '{fn}' is flagged ({rule}) -- add \"force\": true to use anyway")
                if rule.startswith("with:"):
                    needed = set(rule[5:].split("+"))
                    if not needed <= cast:
                        errors.append(f"{where}: '{fn}' shows {sorted(needed)}, not in this episode's cast {sorted(cast)}")
                if i <= HOOK_FRESH_BEATS:
                    warnings.append(f"{where}: hook beat reuses '{fn}' -- the opening should be new images")
                if str(ep - 1) in row["used_in"].split("+"):
                    repeats.append(fn)
            if fn in seen:
                errors.append(f"{where}: '{fn}' is used twice in this video")
            seen.add(fn)
            uses.setdefault(fn, []).append(i)
        for fn, idx in uses.items():
            idx.sort()
            if len(idx) > MAX_USES:
                errors.append(f"{version}: '{fn}' covers {len(idx)} beats {idx} (max {MAX_USES})")
            close = [(a, b) for a, b in zip(idx, idx[1:]) if b - a < MIN_GAP]
            if close:
                errors.append(f"{version}: '{fn}' repeats too close together at beats {close} (min gap {MIN_GAP})")
    if repeats:
        warnings.append(f"{len(repeats)} reused image(s) also appeared in ep{ep - 1} -- fine early on, "
                        "prefer older pool images as the pool grows")
    desc = spec.get("package", {}).get("long", {}).get("app_description", "")
    if len(desc) > DESCRIPTION_LIMIT:
        errors.append(f"package.long.app_description is {len(desc)} chars (app limit {DESCRIPTION_LIMIT})")
    return errors, warnings


def cmd_prompts(ep, out_dir=None):
    spec, pool = load_spec(ep), load_pool()
    errors, warnings = validate(spec, pool)
    for w in warnings:
        print("WARN ", w)
    if errors:
        for e in errors:
            print("ERROR", e)
        sys.exit(1)
    out = Path(out_dir) if out_dir else ROOT
    # A version whose images already exist keeps its CSV: the pool reads each image's style from it.
    locked = {v for v in ("long", "short")
              if out == ROOT and images_dir(ep, v).exists() and any(images_dir(ep, v).glob("*.png"))}
    extra = spec.get("characters", {})
    lines = [f"# Biblical Figures -- Tap {ep} -- {spec['figure']}", ""]
    for version in ("long", "short"):
        beats = spec.get(version, [])
        rows = []
        if version == "long" and spec.get("thumbnail"):
            th = spec["thumbnail"]
            rows.append(["T", f"ep{ep}_thumbnail_{th['stem']}.png", "(THUMBNAIL - khong import, upload len YouTube)",
                         build_prompt("thumb", th["scene"], th.get("chars", []), extra)])
        if version == "long" and spec.get("reference"):
            ref = spec["reference"]
            rows.append([0, f"000_ref_ep{ep}_{ref['stem']}.png", "(KHONG import - chi dung lam anh tham chieu khoa mat)",
                         build_prompt("long", ref["scene"], ref.get("chars", []), extra)])
        table = []
        for i, beat in enumerate(beats, 1):
            if "new" in beat:
                n = beat["new"]
                fn = new_filename(ep, version, i, n)
                rows.append([i, fn, n["tags"], build_prompt(version, n["scene"], n.get("chars", []), extra)])
                table.append(f"| {i} | {fn} | {beat['narration']} |")
            elif "repeat" in beat:
                table.append(f"| {i} | (lap lai) {image_of(ep, version, beats, i)} | {beat['narration']} |")
            else:
                table.append(f"| {i} | (dung lai) {beat['reuse']} | {beat['narration']} |")
        if version in locked:
            print(f"{version}: images already generated -- kept the existing CSV")
        else:
            write_csv(out / f"biblical_figures_ep{ep}_{version}_scenes.csv", rows)
        images_dir(ep, version).mkdir(exist_ok=True)
        words = sum(len(b["narration"].split()) for b in beats)
        n_new = sum("new" in b for b in beats)
        lines += [f"## {version.upper()} ({'16:9' if version == 'long' else '9:16'})", "",
                  f"{len(beats)} beats, {words} words (~{words / WPM[version]:.1f} min) -- "
                  f"**{n_new} anh moi**, {sum('repeat' in b for b in beats)} beat lap lai anh trong tap, "
                  f"{sum('reuse' in b for b in beats)} anh dung lai tu kho.", "",
                  "| # | Anh | Narration |", "|---|---|---|", *table, ""]
        print(f"{version}: {len(beats)} beats, {n_new} new images, {sum('repeat' in b for b in beats)} repeats, "
              f"{sum('reuse' in b for b in beats)} pool reuses, "
              f"~{words / WPM[version] * 60:.0f}s narration")
    if spec.get("sources"):
        lines += ["## Nguon (de doi chieu khi duyet)", "", *[f"- {s}" for s in spec["sources"]], ""]
    (out / f"biblical_figures_ep{ep}_script.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    pkg = spec.get("package", {})
    txt = [f"BIBLICAL FIGURES -- TAP {ep} -- {spec['figure'].upper()} -- TITLE & DESCRIPTION", ""]
    for version in ("long", "short"):
        p = pkg.get(version)
        if p:
            txt += [f"---------------- {version.upper()} ----------------", "", "TITLE:", p["title"], "",
                    "DESCRIPTION (dan len YouTube):", p["description"], "",
                    "HASHTAGS:", ", ".join(p["hashtags"]), ""]
    (out / f"biblical_figures_ep{ep}_title_description.txt").write_text("\n".join(txt), encoding="utf-8", newline="\n")
    print(f"written to {out}")


# -- build -----------------------------------------------------------------

def version_config(cfg, version, spec):
    if version == "long":
        cfg["render"]["profile"] = "SOCIAL_LANDSCAPE"
        cfg["motion"].update({"default_preset": "SLOW_PUSH_IN", "intensity": "MEDIUM", "auto_rotate": True})
        cfg["captions"].update({"enabled": True, "preset": "cinematic"})
        cfg["voice"].update({"speed": 0.95, "sentence_pause_sec": 0.5})
        cfg["outro"].update({"enabled": True, "text": "If you made it this far, subscribe -- a new figure from history every week."})
    else:
        # 2026-09-29: Short now borrows the manhua-series template's own look
        # (backend/app/modules/beat/schemas.py _MANHUA_CAPTIONS/manhua_ai_vi's motion) --
        # word_pop (one coloured word at a time) reads better on a phone than word_highlight's
        # multi-word cards, and the gentler SLOW_PUSH_IN/MEDIUM push matches it (ZOOM_AND_PAN/
        # STRONG was tuned for the old cinematic-photoreal look, not painted stills). Voice
        # stays English/Ryan at the biblical_figures rate -- manhua's 1.6/vi-VN-NamMinhNeural
        # is Vietnamese-narrator specific, not part of the "template" being borrowed here.
        cfg["render"]["profile"] = "SOCIAL_VERTICAL"
        cfg["motion"].update({"default_preset": "SLOW_PUSH_IN", "intensity": "MEDIUM", "auto_rotate": True})
        cfg["captions"].update({"enabled": True, "preset": "word_pop", "max_words": 1, "max_chars": 20,
                                "max_lines": 1, "min_duration_sec": 0.15, "max_duration_sec": 1.5})
        cfg["voice"].update({"speed": 1.1, "sentence_pause_sec": 0.2})
        cfg["outro"].update({"enabled": False})
    cfg["voice"].update({"provider": "edge_tts", "voice_id": "en-GB-RyanNeural", "language": "en"})
    cfg["audio"].update({"narration_enabled": True, "music_enabled": False})
    cfg["package"].update({"ai_metadata_enabled": False})
    return cfg


def cmd_build(ep, version):
    spec, pool = load_spec(ep), load_pool()
    errors, _ = validate(spec, pool)
    if errors:
        sys.exit("Spec has errors -- run `python bf.py prompts %d` first.\n" % ep + "\n".join(errors))
    beats_spec = spec[version]
    lib = library_images()
    beats, missing = [], []
    for i, beat in enumerate(beats_spec, 1):
        if "reuse" in beat:
            path = Path(pool[beat["reuse"]]["path"])
        else:
            path = images_dir(ep, version) / image_of(ep, version, beats_spec, i)
        if not path.exists():
            missing.append(path.name)
        beats.append((beat, path))
    if missing:
        sys.exit(f"{len(missing)} image(s) not generated yet: {missing[:10]}")

    from PIL import Image
    out_beats = []
    for i, (beat, path) in enumerate(beats, 1):
        asset = lib.get(str(path).lower())
        if asset is None:  # a new image: register it once, it joins the pool for later episodes
            w, h = Image.open(path).size
            source = beat if "new" in beat else next(b for b in beats_spec if b.get("new", {}).get("stem") == beat["repeat"])
            tags = [t.strip() for t in source["new"]["tags"].split(",") if t.strip()] + ["biblical_figures", f"ep{ep}", version]
            asset = call("POST", "/assets", {"filename": path.name, "path": str(path), "type": "image",
                                             "width": w, "height": h, "tags": tags})
            lib[str(path).lower()] = asset
        text = beat["narration"]
        default_type = "HOOK" if i == 1 else "ENDING" if i == len(beats) else ("BODY" if version == "long" else "BUILD")
        out_beats.append({
            "id": f"b{i}", "order": i, "type": beat.get("type", default_type), "narration": text,
            "duration": round(max(2.0, len(text.split()) / WPM[version] * 60 + 0.4), 2),
            "visual_hint": path.stem, "asset_id": asset["id"],
        })

    name = f"Biblical Figures Ep{ep} {version.upper()} - {spec['figure']}"
    script = " ".join(b["narration"] for b in out_beats)
    pid = call("POST", "/projects", {"name": name, "template_id": "history_documentary", "script_text": script,
                                     "content_language": "en", "visual_generation_mode": "library"})["id"]
    cfg = version_config(call("GET", f"/projects/{pid}")["config"], version, spec)
    cfg["content"]["target_duration"] = float(round(sum(b["duration"] for b in out_beats)))
    call("PUT", f"/projects/{pid}/beat-plan", {"project_name": name, "script_text": script, "script_locked": True,
                                                "beats": out_beats, "config": cfg})
    p = spec.get("package", {}).get(version)
    if p:
        call("PUT", f"/projects/{pid}/package-overrides", {
            "title": p["title"], "description": p.get("app_description") or p["description"], "hashtags": p["hashtags"]})
    run = call("POST", f"/projects/{pid}/factory-run")
    print(f"project {pid} ({name}), factory run {run['id']} {run['status']}")
    cmd_pool()  # new images now have asset ids / usage recorded


def cmd_aigen(ep, version):
    """Generate this video's new images with the app's own image API (gpt-image-1-mini, quality low --
    the model/quality behind the old video that earned views). Skips images that already exist."""
    import os
    backend = ROOT.parent / "backend"
    sys.path.insert(0, str(backend))
    os.chdir(backend)  # Settings reads the app's own .env / data dir relative to the backend
    from app.core.config import get_settings
    from app.modules.ai.image_client import (IMAGE_COST_USD, IMAGE_MODEL, IMAGE_QUALITY, IMAGE_SIZE_LANDSCAPE,
                                             IMAGE_SIZE_PORTRAIT, ImageGenError, generate_beat_image)

    spec, pool = load_spec(ep), load_pool()
    errors, _ = validate(spec, pool)
    if errors:
        sys.exit("Spec has errors:\n" + "\n".join(errors))
    key = get_settings().openai_api_key
    if not key:
        sys.exit("No OpenAI API key configured in the app (Settings).")
    size = IMAGE_SIZE_LANDSCAPE if version == "long" else IMAGE_SIZE_PORTRAIT
    extra = spec.get("characters", {})
    todo = [(i, b) for i, b in enumerate(spec[version], 1) if "new" in b
            and not (images_dir(ep, version) / new_filename(ep, version, i, b["new"])).exists()]
    print(f"{IMAGE_MODEL} / {IMAGE_QUALITY} / {size}: {len(todo)} image(s) to generate "
          f"(~${len(todo) * IMAGE_COST_USD:.2f})")
    # One image's own moderation/API failure must never abort the rest of the batch -- retrying
    # bf.py aigen later only regenerates what's still missing anyway (see `todo` above), so the
    # failed one is simply retried on the next call, ideally after tweaking its scene text.
    failed = []
    for n, (i, b) in enumerate(todo, 1):
        out = images_dir(ep, version) / new_filename(ep, version, i, b["new"])
        try:
            generate_beat_image(key, build_prompt(version, b["new"]["scene"], b["new"].get("chars", []), extra), out, size=size)
        except ImageGenError as exc:
            failed.append(out.name)
            print(f"  [{n}/{len(todo)}] FAILED {out.name}: {exc}")
            continue
        print(f"  [{n}/{len(todo)}] {out.name}")
    if failed:
        print(f"{len(failed)} image(s) failed -- reword their scene text if it's a moderation block, "
              f"then re-run aigen: {failed}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["pool"]:
        cmd_pool()
    elif args[:1] == ["prompts"] and len(args) >= 2:
        cmd_prompts(int(args[1]), args[2] if len(args) > 2 else None)
    elif args[:1] == ["aigen"] and len(args) == 3 and args[2] in ("long", "short"):
        cmd_aigen(int(args[1]), args[2])
    elif args[:1] == ["build"] and len(args) == 3 and args[2] in ("long", "short"):
        cmd_build(int(args[1]), args[2])
    else:
        sys.exit(__doc__)
