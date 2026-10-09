"""Build one documentary episode in the app from a spec file, WITHOUT approving anything.

The spec (see ../templates/spec_template.json and ../examples/) holds sources, claims, the script
and the images. This tool only does the typing; every approval gate stays with a human in the app.

  python episode_builder.py create     spec.json   # project + sources (verbatim excerpts) + claims + script draft
  python episode_builder.py storyboard spec.json   # plan scenes, apply scene_overrides   (needs gate 2 approved)
  python episode_builder.py images     spec.json   # fetch/import images, assign them     (images stay PENDING)
  python episode_builder.py status     spec.json

Environment: DOC_API (default http://127.0.0.1:8000/api/v1/documentary).
State (project id, asset ids) is kept in <spec>.state.json next to the spec.
Run the backend from a scratch working directory when experimenting: settings endpoints write the
real backend/.env relative to the backend's cwd.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commons  # noqa: E402

API = os.environ.get("DOC_API", "http://127.0.0.1:8000/api/v1/documentary")


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {method} {path}: {e.read().decode('utf-8', 'replace')[:500]}")


# -- state ---------------------------------------------------------------------------------------
def load_spec(arg: str) -> tuple[dict, Path, dict]:
    path = Path(arg).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    sp = path.with_suffix(".state.json")
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {}
    return spec, path, state


def save_state(path: Path, state: dict) -> None:
    path.with_suffix(".state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# -- verbatim excerpts ---------------------------------------------------------------------------
def wiki_text(spec: dict, cache: Path) -> str:
    w = spec["wiki"]
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"wiki_{w['lang']}_{w['title']}.txt"
    if not f.is_file():
        url = (f"https://{w['lang']}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&exsectionformat=plain"
               f"&titles={urllib.parse.quote(w['title'])}&format=json&redirects=1")
        req = urllib.request.Request(url, headers=commons.UA)
        d = json.load(urllib.request.urlopen(req, timeout=60))
        f.write_text(next(iter(d["query"]["pages"].values()))["extract"], encoding="utf-8")
    return f.read_text(encoding="utf-8")


def excerpt(text: str, needles: list[str]) -> str:
    """Whole sentences of the article that contain each needle -- cut, never retyped."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    out = []
    for n in needles:
        para = next((p for p in paras if n in p), None)
        if para is None:
            raise SystemExit(f"Needle not found in the article (fix the spec, do not paraphrase): {n!r}")
        core = n.rstrip(".!?")  # sentences are split on ". ", which eats the full stop of every piece but the last
        sent = next((s.strip() for s in para.split(". ") if core in s), para)
        out.append(sent if sent.endswith(".") else sent + ".")
    return " ".join(out)


def fetch_source(s: dict, cache: Path) -> dict:
    """Primary-text sources beyond the spec's default Wikipedia article. Always cut, never retyped.
      {"fetch": {"kind": "bible", "ref": "Mark 6:17-29"}}      World English Bible (public domain) via bible-api.com
      {"fetch": {"kind": "wikisource", "page": "...", "needles": [...]}}   a Wikisource page (e.g. Whiston's Josephus)
      {"fetch": {"kind": "wikipedia", "lang": "en", "title": "...", "needles": [...]}}   another article
    -> {"excerpt", "url", "publisher", "author"} (spec keys url/publisher/author/accessed override)."""
    f = s["fetch"]
    kind = f["kind"]
    cache.mkdir(parents=True, exist_ok=True)
    if kind == "bible":
        ref = f["ref"]
        cf = cache / ("bible_" + re.sub(r"\W+", "_", ref) + ".json")
        if not cf.is_file():
            url = "https://bible-api.com/" + urllib.parse.quote(ref) + "?translation=web"
            cf.write_text(urllib.request.urlopen(urllib.request.Request(url, headers=commons.UA), timeout=60).read().decode("utf-8"), encoding="utf-8")
        d = json.loads(cf.read_text(encoding="utf-8"))
        text = " ".join(v["text"].strip().replace("\n", " ") for v in d["verses"])
        return {"excerpt": text, "url": "https://bible-api.com/" + urllib.parse.quote(ref) + "?translation=web",
                "publisher": "World English Bible (public domain)", "author": "Biblical text"}
    if kind == "wikisource":
        page = f["page"]
        cf = cache / ("wikisource_" + f.get("lang", "en") + "_" + re.sub(r"\W+", "_", page) + ".txt")
        if not cf.is_file():
            import html as _html
            lang = f.get("lang", "en")
            url = (f"https://{lang}.wikisource.org/w/api.php?action=parse&page=" + urllib.parse.quote(page, safe="/")
                   + "&prop=text&format=json&formatversion=2&disabletoc=1")
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=commons.UA), timeout=120))
            cf.write_text(_html.unescape(re.sub(r"<[^>]+>", "", d["parse"]["text"])), encoding="utf-8")
        return {"excerpt": excerpt(cf.read_text(encoding="utf-8"), f["needles"]), "url": f"https://{f.get('lang', 'en')}.wikisource.org/wiki/" + urllib.parse.quote(page, safe="/"),
                "publisher": f.get("publisher", "Wikisource (William Whiston translation, public domain)"), "author": f.get("author", "Flavius Josephus")}
    if kind == "wikipedia":
        w = {"lang": f.get("lang", "en"), "title": f["title"]}
        return {"excerpt": excerpt(wiki_text({"wiki": w}, cache), f["needles"]), "url": f"https://{w['lang']}.wikipedia.org/wiki/{w['title']}",
                "publisher": "Wikimedia Foundation", "author": "Wikipedia contributors"}
    raise SystemExit(f"unknown fetch kind {kind!r}")


# -- commands ----------------------------------------------------------------------------------------
def cmd_create(spec_arg: str) -> None:
    spec, path, state = load_spec(spec_arg)
    if state.get("project_id"):
        raise SystemExit(f"Already created (project {state['project_id']}). Delete {path.with_suffix('.state.json').name} to start over.")
    w = spec.get("wiki")
    text = wiki_text(spec, path.parent / ".cache") if w else ""
    page_url = f"https://{w['lang']}.wikipedia.org/wiki/{w['title']}" if w else None
    w = w or {"accessed": spec["accessed"], "publisher": ""}
    pid = call("POST", "/projects", {"title": spec["title"], "topic": spec["topic"], "budget_usd": spec.get("budget_usd"), "language": spec.get("language", "vi")})["id"]
    state["project_id"] = pid
    src_ids, claim_ids = {}, {}
    for s in spec["sources"]:
        got = fetch_source(s, path.parent / ".cache") if s.get("fetch") else {
            "excerpt": excerpt(text, s["needles"]), "url": page_url, "publisher": w.get("publisher", "Wikimedia Foundation"), "author": "Wikipedia contributors"}
        src_ids[s["key"]] = call("POST", f"/projects/{pid}/sources", {
            "title": s["title"], "url": s.get("url", got["url"]), "publisher": s.get("publisher", got["publisher"]), "author": s.get("author", got["author"]),
            "accessed_date": s.get("accessed", w["accessed"]), "excerpt": got["excerpt"],
            "notes": s.get("notes", "Nguồn thứ cấp: đối chiếu thêm sách chuyên khảo trước khi đăng."),
        })["id"]
    for c in spec["claims"]:
        claim_ids[c["key"]] = call("POST", f"/projects/{pid}/claims", {
            "text": c["text"], "status": c["status"], "uncertainty_note": c.get("note"), "source_ids": [src_ids[k] for k in c["sources"]],
        })["id"]
    sections = [{"kind": sec["kind"], "heading": sec["heading"], "paragraphs": [
        {"text": p["text"], "factual": p.get("factual", True), "claim_ids": [claim_ids[k] for k in p.get("claims", [])]} for p in sec["paragraphs"]
    ]} for sec in spec["script"]]
    script = call("PUT", f"/projects/{pid}/script", {"outline": [], "sections": sections})
    review = call("GET", f"/projects/{pid}/script/review")
    state.update(sources=src_ids, claims=claim_ids)
    save_state(path, state)
    print(f"project {pid}: {len(src_ids)} sources, {len(claim_ids)} claims, script v{script['version']} "
          f"({script['word_count']} words, ~{script['estimated_seconds']}s estimated)")
    print("script review:", "OK" if review["ok"] else review["issues"])
    print("NEXT (human): open the project in the app -> approve gate 1 (research), advance, approve gate 2 (script), advance to storyboard_review.")


def cmd_storyboard(spec_arg: str) -> None:
    spec, path, state = load_spec(spec_arg)
    pid = state["project_id"]
    print("plan:", call("POST", f"/projects/{pid}/storyboard/plan"))
    scenes = {s["scene_key"]: s for s in call("GET", f"/projects/{pid}/scenes")}
    for key, ov in spec.get("scene_overrides", {}).items():
        if key not in scenes:
            print(f"  ! scene {key} does not exist any more (narration changed?) - skipped")
            continue
        body = {}
        if ov.get("preset"):
            body["visual_preset"] = ov["preset"]
        if ov.get("objective"):
            body["visual_objective"] = ov["objective"]
        if ov.get("texts") is not None:
            body["on_screen_text"] = [{"text": t, "role": r} for t, r in ov["texts"]]
        call("PUT", f"/projects/{pid}/scenes/{scenes[key]['id']}", body)
    print("re-plan (assign image groups):", call("POST", f"/projects/{pid}/storyboard/plan"))
    for s in call("GET", f"/projects/{pid}/scenes"):
        print(f"  {s['scene_key']} {s['visual_preset']:<16} {s['asset_strategy']:<12} {s['narration_text'][:60]}")


def cmd_images(spec_arg: str) -> None:
    spec, path, state = load_spec(spec_arg)
    pid = state["project_id"]
    cache = path.parent / ".cache" / "images"
    cache.mkdir(parents=True, exist_ok=True)
    scenes = {s["scene_key"]: s for s in call("GET", f"/projects/{pid}/scenes")}
    assets = state.setdefault("assets", {})
    for img in spec.get("images", []):
        key = img["key"]
        if key not in assets:
            if img["kind"] == "commons":
                dest = cache / f"{key}.jpg"
                meta = commons.download(img["commons_title"], dest)
                a = call("POST", f"/projects/{pid}/assets/import", {
                    "path": str(dest), "origin": "archival", "license": meta["license"], "attribution": f"{commons._plain(meta['artist']) or 'Unknown'} — Wikimedia Commons",
                    "source_url": meta["page"], "tags": [key]})
                note = "  <-- READ THIS LICENCE BEFORE APPROVING" if meta["needs_review"] else ""
                print(f"imported {key}: {meta['license']}{note}")
            elif img["kind"] == "file":
                a = call("POST", f"/projects/{pid}/assets/import", {
                    "path": str(Path(img["path"]).expanduser()), "origin": img.get("origin", "imported"), "license": img.get("license"),
                    "attribution": img.get("attribution"), "source_url": img.get("source_url"), "tags": [key]})
                print(f"imported {key} from file")
            else:
                raise SystemExit(f"unknown image kind {img['kind']!r}")
            assets[key] = a["id"]
        use = list(img.get("use", []))
        if img.get("paragraphs"):  # 1-based script paragraphs; the scenes cut from them get this image (max 3 per image)
            flat = [p["text"] for sec in spec["script"] for p in sec["paragraphs"]]
            for n in img["paragraphs"]:
                got = [k for k, sc in scenes.items() if sc["narration_text"].strip() in flat[n - 1]]
                if len(got) > 3:
                    print(f"  ! paragraph {n} has {len(got)} scenes but one image serves at most 3 - {got[3:]} need another image")
                use += got[:3]
        for sk in use:
            if sk in scenes and scenes[sk].get("asset_strategy") != "programmatic":  # data cards need no image
                call("PUT", f"/projects/{pid}/scenes/{scenes[sk]['id']}/asset", {"asset_id": assets[key]})
    save_state(path, state)
    print("All images are PENDING. NEXT (human): open the 'Ảnh' tab, read each licence, approve/reject.")


def cmd_status(spec_arg: str) -> None:
    _spec, _path, state = load_spec(spec_arg)
    pid = state["project_id"]
    p = call("GET", f"/projects/{pid}")
    print(f"project {pid}: {p['state']}", [(g["gate"], g["status"]) for g in p["gates"]])


COMMANDS = {"create": cmd_create, "storyboard": cmd_storyboard, "images": cmd_images, "status": cmd_status}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        raise SystemExit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2])
