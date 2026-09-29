"""Story Remix tool -- 1-3 trending "xuyên không"/"hệ thống" YouTube storytelling
videos -> transcribed, then substantially rewritten into one new chapter for the
built-in "isekai_system_vi" template.

Usage (backend running, with the backend venv's python):
    python remix.py fetch  <batch> <url1> [url2] [url3] [--source-lang vi]
                                                          # download each source video via the
                                                          # existing Download API, transcribe it,
                                                          # write <batch>/_remix/sources.json
    python remix.py script <batch> [--lang vi|ko] [--notes "..."]
                                                          # AI rewrites the sources into one new
                                                          # chapter, writes <batch>/_remix/script.json
    python remix.py build  <batch> [--script FILE] [--name "..."] [--no-render]
                                                          # create the project, PUT the beat plan,
                                                          # start the render

<batch> is a plain folder name under story-remix/ (created on first `fetch`). Between
steps you can hand-edit _remix/script.json (title / new_setting / beat narration+visuals)
before `build` -- confirm the character names, setting and ending really are new, not a
close paraphrase of the sources. The project uses the built-in "isekai_system_vi" template.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = os.environ.get("STORY_REMIX_API", "http://127.0.0.1:8000/api/v1")  # override to target another backend
TEMPLATE_ID = "isekai_system_vi"
BATCH_ROOT = ROOT.parent.parent / "story-remix"

# Generic prose narration pace (news_pipeline.py's own constants) -- the pre-voice
# duration estimate only; the Voice stage re-times every beat to the real
# synthesized narration once it runs.
WORDS_PER_SEC = 2.3
MIN_BEAT_SEC = 1.8
MAX_BEAT_SEC = 12.0

DOWNLOAD_POLL_SEC = 2.0
DOWNLOAD_TIMEOUT_SEC = 1800


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


def _batch_dir(batch: str) -> Path:
    return BATCH_ROOT / batch


# -- fetch (download + transcribe) -----------------------------------------------

def _detect_and_enqueue(url: str) -> dict:
    result = call("POST", "/detect", {"url": url})
    if result.get("contentType") != "video":
        sys.exit(f"{url} is a playlist/channel, not a single video -- paste a single video URL.")
    video = result["video"]
    metadata = {
        "platform": result["platform"], "video_id": video["id"], "channel_name": video["author"],
        "title": video["title"], "original_url": video["originalUrl"], "thumbnail_url": video["thumbnailUrl"],
        "views": video["views"], "duration_sec": video["durationSec"], "upload_date": video["uploadDate"],
    }
    return call("POST", "/downloads", {"url": video["originalUrl"], "metadata": metadata})


def _wait_for_download(task_id: int) -> str:
    start = time.time()
    while time.time() - start < DOWNLOAD_TIMEOUT_SEC:
        task = call("GET", f"/downloads/{task_id}")
        status = task["status"]
        if status == "completed":
            path = task["video"]["video_path"]
            if not path:
                sys.exit(f"download {task_id} completed but has no video_path")
            print()
            return path
        if status in ("failed", "cancelled"):
            sys.exit(f"download {task_id} {status}: {task.get('error_message')}")
        print(f"\r  download {task_id}: {status} {task.get('progress_pct') or 0:.0f}%", end="", flush=True)
        time.sleep(DOWNLOAD_POLL_SEC)
    sys.exit(f"download {task_id} timed out after {DOWNLOAD_TIMEOUT_SEC}s")


def cmd_fetch(batch: str, urls: list[str], source_lang: str) -> None:
    if not 1 <= len(urls) <= 3:
        sys.exit("Give 1-3 source video URLs.")
    chapter = _batch_dir(batch)
    sources = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        task = _detect_and_enqueue(url)
        print(f"  queued as download {task['id']}, waiting...")
        video_path = _wait_for_download(task["id"])
        print(f"  downloaded -> {video_path}, transcribing...")
        result = call("POST", "/story-remix/transcribe", {"video_path": video_path, "language": source_lang}, timeout=600)
        sources.append({
            "url": url, "video_path": video_path, "language": source_lang, "label": f"source {i}",
            "text": result["text"], "duration_sec": result["duration_sec"], "cost_usd": result["cost_usd"],
        })
        print(f"  {len(result['text'])} chars transcribed, ~${result['cost_usd'] or 0:.4f}")

    path = chapter / "_remix" / "sources.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(sources)} source(s) -> {path}. Next: `script`.")


# -- script (AI rewrite) ----------------------------------------------------------

def cmd_script(batch: str, target_lang: str, notes: str | None) -> None:
    chapter = _batch_dir(batch)
    sources_path = chapter / "_remix" / "sources.json"
    if not sources_path.exists():
        sys.exit(f"No sources at {sources_path} -- run `fetch` first.")
    sources = json.loads(sources_path.read_text(encoding="utf-8"))["sources"]

    print(f"Rewriting {len(sources)} source(s) into a new {target_lang} chapter (this can take a minute)...")
    payload_sources = [{"text": s["text"], "language": s["language"], "label": s["label"]} for s in sources]
    result = call("POST", "/story-remix/rewrite", {
        "sources": payload_sources, "target_language": target_lang, "notes": notes,
    }, timeout=300)

    script = {
        "title": result["title"], "new_setting": result["new_setting"], "language": target_lang,
        "transformation": result["transformation"], "beats": result["beats"],
    }
    path = chapter / "_remix" / "script.json"
    path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    t = script["transformation"]
    print(f"\n{script['title']}\nsetting: {script['new_setting']}")
    print(f"transformation: renamed={t['renamed_characters']} setting={t['changed_setting']} "
          f"ending={t['changed_ending']} blended={t['blended_sources']}")
    print(f"{len(script['beats'])} beats -> {path}")
    for b in script["beats"]:
        print(f"  [{b['type']}] {b['narration']}")
    print("\nReview script.json -- confirm the names/setting/ending really are new -- then run `build`.")


# -- build (project + beat-plan + render) ------------------------------------------

def cmd_build(batch: str, script_path: Path | None, name: str | None, render: bool) -> None:
    chapter = _batch_dir(batch)
    script_path = script_path or chapter / "_remix" / "script.json"
    if not script_path.exists():
        sys.exit(f"No script at {script_path} -- run `script` (or write one by hand) first.")
    script = json.loads(script_path.read_text(encoding="utf-8"))

    beats = []
    for i, b in enumerate(script["beats"], 1):
        text = b["narration"].strip()
        duration = round(min(MAX_BEAT_SEC, max(MIN_BEAT_SEC, len(text.split()) / WORDS_PER_SEC + 0.3)), 2)
        beats.append({
            "id": f"b{i}", "order": i, "type": b.get("type", "BUILD"),
            "narration": text, "duration": duration,
            "visual_hint": b.get("visual_hint"), "visual_description": b.get("visual_description"),
        })

    name = name or script["title"]
    text = " ".join(b["narration"] for b in beats)
    pid = call("POST", "/projects", {
        "name": name, "template_id": TEMPLATE_ID, "script_text": text,
        "content_language": script.get("language", "vi"),
        # The Beat module defaults every new project to "library" mode
        # regardless of the chosen template's own config (see
        # CreateProjectRequest.visual_generation_mode) -- this niche has no
        # reused asset pool, so every beat must generate a fresh AI image.
        "visual_generation_mode": "ai_generated",
    })["id"]
    cfg = call("GET", f"/projects/{pid}")["config"]
    cfg["content"]["target_duration"] = float(round(sum(b["duration"] for b in beats)))
    call("PUT", f"/projects/{pid}/beat-plan", {
        "project_name": name, "script_text": text, "script_locked": True, "beats": beats, "config": cfg,
    })
    call("PUT", f"/projects/{pid}/package-overrides", {"title": script["title"][:70]})

    if not render:
        print(f"project {pid} ({name}) created -- open it in the app to render.")
        return
    run = call("POST", f"/projects/{pid}/factory-run")
    print(f"project {pid} ({name}), factory run {run['id']} {run['status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch = sub.add_parser("fetch")
    fetch.add_argument("batch")
    fetch.add_argument("urls", nargs="+")
    fetch.add_argument("--source-lang", default="vi", help="spoken language of the source video(s)")

    script = sub.add_parser("script")
    script.add_argument("batch")
    script.add_argument("--lang", default="vi", choices=("vi", "ko"), help="target narration language")
    script.add_argument("--notes", default=None, help="context the transcripts can't give (trope, tone, ...)")

    build = sub.add_parser("build")
    build.add_argument("batch")
    build.add_argument("--script", type=Path, default=None,
                        help="script.json to build from (default <batch>/_remix/script.json)")
    build.add_argument("--name", default=None)
    build.add_argument("--no-render", action="store_true")

    args = parser.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(args.batch, args.urls, args.source_lang)
    elif args.cmd == "script":
        cmd_script(args.batch, args.lang, args.notes)
    else:
        cmd_build(args.batch, args.script.resolve() if args.script else None, args.name, not args.no_render)


if __name__ == "__main__":
    main()
