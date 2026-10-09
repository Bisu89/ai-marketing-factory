"""Render jobs: Remotion draws the picture, ffmpeg adds the narration, ffprobe and a
black-frame scan check the result.

One job = one background thread; only one render runs at a time (they are CPU
heavy). A job whose input hash matches a finished one is not rendered again. A
failed or interrupted job is simply re-run -- partial resume is not supported, and
this module says so rather than pretending: the cheap parts (asset copy, manifest)
are recomputed, the frame rendering starts over.

No shell is ever involved: every command is an argument list built from our own
data, never from user-supplied strings.
"""

from __future__ import annotations

import json
import logging
import math
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.documentary import media
from app.modules.documentary.models import DocumentaryRenderJob, DocumentarySceneTiming
from app.modules.documentary.render_plan import FPS, HEIGHT, REMOTION_DIR, WIDTH, RenderParams, build_manifest, preflight
from app.modules.documentary.schemas import ReviewIssue, ReviewOut

logger = logging.getLogger(__name__)

_LOCK = threading.Semaphore(1)  # one render at a time
_THREADS: dict[int, threading.Thread] = {}
_PROCS: dict[int, subprocess.Popen] = {}
_CANCEL: set[int] = set()

RENDER_TIMEOUT_SEC = 3 * 60 * 60
BLACK_MIN_SEC = 0.15
DURATION_TOL_SEC = 0.12


def tools() -> dict[str, str | None]:
    return {name: shutil.which(name) for name in ("node", "npx", "ffmpeg", "ffprobe")}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RenderService:
    def __init__(self, db: Session, root: Path, session_factory: Callable[[], Session] | None = None):
        self.db = db
        self.root = root
        self._session_factory = session_factory

    # -- paths ---------------------------------------------------------------
    def project_dir(self, project_id: int) -> Path:
        return self.root / "_documentary" / f"project_{project_id}" / "render"

    def job_dir(self, project_id: int, job_id: int) -> Path:
        return self.project_dir(project_id) / f"job_{job_id}"

    # -- reading -----------------------------------------------------------------
    def get(self, project_id: int, job_id: int) -> DocumentaryRenderJob:
        job = self.db.get(DocumentaryRenderJob, job_id)
        if job is None or job.project_id != project_id:
            raise NotFoundError("render job", job_id)
        self._reconcile(job)
        return job

    def list(self, project_id: int) -> list[DocumentaryRenderJob]:
        jobs = list(
            self.db.scalars(
                select(DocumentaryRenderJob).where(DocumentaryRenderJob.project_id == project_id).order_by(DocumentaryRenderJob.id.desc())
            )
        )
        for j in jobs:
            self._reconcile(j)
        return jobs

    def _reconcile(self, job: DocumentaryRenderJob) -> None:
        """A job marked running/queued with no live thread was interrupted (app restart)."""
        if job.status in ("queued", "running") and not (_THREADS.get(job.id) and _THREADS[job.id].is_alive()):
            job.status, job.error, job.finished_at = "failed", "Bị gián đoạn (ứng dụng đã khởi động lại) — hãy chạy lại.", _now()
            self.db.commit()

    def log_tail(self, job: DocumentaryRenderJob, lines: int = 120) -> str:
        if not job.log_path or not Path(job.log_path).is_file():
            return ""
        return "".join(Path(job.log_path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-lines:])

    # -- preflight -------------------------------------------------------------------
    def preflight(self, project_id: int) -> list[ReviewIssue]:
        t = tools()
        return preflight(self.db, self.root, project_id, {"node": bool(t["node"] and t["npx"]), "ffmpeg": bool(t["ffmpeg"] and t["ffprobe"])})

    # -- start / cancel -----------------------------------------------------------------
    def start(self, project_id: int, params: RenderParams) -> tuple[DocumentaryRenderJob, bool]:
        """-> (job, reused). Raises ValidationError listing every blocking problem."""
        if params.kind not in ("preview", "final"):
            raise ValidationError("kind phải là 'preview' hoặc 'final'.")
        if params.kind == "final" and (params.scale != 1.0 or params.seconds is not None):
            raise ValidationError("Bản final luôn là 1920×1080 và đủ độ dài (scale=1, không rút ngắn).")
        if not (0.2 <= params.scale <= 1.0):
            raise ValidationError("scale phải trong khoảng 0.2–1.0.")
        if params.seconds is not None and params.seconds <= 0:
            raise ValidationError("seconds phải > 0.")
        issues = self.preflight(project_id)
        if issues:
            raise ValidationError("Chưa thể render: " + "; ".join(i.message for i in issues[:8]) + ("…" if len(issues) > 8 else ""))
        _manifest, _public, digest = build_manifest(self.db, self.root, project_id, params)

        for existing in self.db.scalars(
            select(DocumentaryRenderJob).where(
                DocumentaryRenderJob.project_id == project_id, DocumentaryRenderJob.input_hash == digest, DocumentaryRenderJob.kind == params.kind
            ).order_by(DocumentaryRenderJob.id.desc())
        ):
            self._reconcile(existing)
            if existing.status in ("queued", "running"):
                return existing, True
            if existing.status == "succeeded" and existing.output_path and Path(existing.output_path).is_file():
                return existing, True

        job = DocumentaryRenderJob(project_id=project_id, kind=params.kind, status="queued", input_hash=digest, params=params.to_json())
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        factory = self._session_factory
        if factory is None:
            from app.db.session import SessionLocal

            factory = SessionLocal
        th = threading.Thread(target=_execute, args=(factory, self.root, job.id), name=f"doc-render-{job.id}", daemon=True)
        _THREADS[job.id] = th
        th.start()
        return job, False

    def cancel(self, project_id: int, job_id: int) -> DocumentaryRenderJob:
        job = self.get(project_id, job_id)
        if job.status not in ("queued", "running"):
            raise ValidationError(f"Job đang ở trạng thái '{job.status}', không thể hủy.")
        _CANCEL.add(job.id)
        proc = _PROCS.get(job.id)
        if proc is not None and proc.poll() is None:
            proc.kill()
        return job

    # -- gate 5 ----------------------------------------------------------------------------
    def final_review(self, project_id: int) -> ReviewOut:
        jobs = [j for j in self.list(project_id) if j.kind == "final" and j.status == "succeeded"]
        if not jobs:
            return ReviewOut(ok=False, issues=[ReviewIssue(code="no_final_render", message="Chưa có bản render final thành công.")])
        job = jobs[0]
        if not job.output_path or not Path(job.output_path).is_file():
            return ReviewOut(ok=False, issues=[ReviewIssue(code="render_file_missing", message="File video final không còn trên đĩa — hãy render lại.")])
        p = job.params
        params = RenderParams(
            kind="final", scale=1.0, seconds=None, burn_subtitles=p.get("burn_subtitles", True),
            grayscale=p.get("grayscale", True), normalize_audio=p.get("normalize_audio", True),
        )
        try:
            _m, _pub, digest = build_manifest(self.db, self.root, project_id, params)
        except ValidationError as exc:
            return ReviewOut(ok=False, issues=[ReviewIssue(code="render_inputs_invalid", message=str(exc))])
        issues: list[ReviewIssue] = []
        if digest != job.input_hash:
            issues.append(ReviewIssue(code="render_stale", message="Dữ liệu đã đổi sau lần render final gần nhất — hãy render lại."))
        qc = job.qc or {}
        for i in qc.get("issues", []):
            issues.append(ReviewIssue(code=i.get("code", "qc"), message=i.get("message", "")))
        warnings = [ReviewIssue(code=w.get("code", "qc"), message=w.get("message", "")) for w in qc.get("warnings", [])]
        return ReviewOut(ok=not issues, issues=issues, warnings=warnings)


# =====================================================================================
# Worker (runs in its own thread with its own DB session)
# =====================================================================================
def _log(fh, msg: str) -> None:
    fh.write(msg.rstrip("\n") + "\n")
    fh.flush()


def _update(db: Session, job: DocumentaryRenderJob, **fields) -> None:
    for k, v in fields.items():
        setattr(job, k, v)
    db.commit()


def _execute(session_factory: Callable[[], Session], root: Path, job_id: int) -> None:
    db = session_factory()
    try:
        _LOCK.acquire()
        try:
            job = db.get(DocumentaryRenderJob, job_id)
            if job is None:
                return
            if job_id in _CANCEL:
                _update(db, job, status="cancelled", finished_at=_now())
                return
            _run_job(db, root, job)
        finally:
            _LOCK.release()
    except Exception as exc:  # noqa: BLE001 -- a worker must never die silently
        logger.exception("documentary render job %s crashed", job_id)
        try:
            db.rollback()
            job = db.get(DocumentaryRenderJob, job_id)
            if job is not None and job.status not in ("succeeded", "cancelled"):
                _update(db, job, status="failed", error=f"{type(exc).__name__}: {str(exc)[:400]}", finished_at=_now())
        except Exception:  # noqa: BLE001
            logger.exception("could not record failure of render job %s", job_id)
    finally:
        _PROCS.pop(job_id, None)
        _CANCEL.discard(job_id)
        db.close()


def _run_job(db: Session, root: Path, job: DocumentaryRenderJob) -> None:
    svc = RenderService(db, root)
    p = job.params
    params = RenderParams(
        kind=job.kind, scale=p["scale"], seconds=p["seconds"], burn_subtitles=p["burn_subtitles"],
        grayscale=p["grayscale"], normalize_audio=p["normalize_audio"],
    )
    jdir = svc.job_dir(job.project_id, job.id)
    jdir.mkdir(parents=True, exist_ok=True)
    log_path = jdir / "render.log"
    _update(db, job, status="running", phase="preparing", progress=0.02, log_path=str(log_path), error=None)

    with log_path.open("w", encoding="utf-8") as log:
        manifest, public, digest = build_manifest(db, root, job.project_id, params)
        if digest != job.input_hash:
            raise ValidationError("Dữ liệu đã đổi giữa lúc xếp hàng và lúc chạy — hãy bấm render lại.")
        public_dir = jdir / "public"
        for rel, src in public.items():
            dest = public_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        props = jdir / "props.json"
        props.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        total_frames = manifest["durationInFrames"]
        last_frame = total_frames - 1
        if params.seconds is not None:
            last_frame = min(last_frame, math.ceil(params.seconds * FPS) - 1)
        silent = jdir / "video_silent.mp4"
        _log(log, f"[{_now().isoformat()}] job {job.id} {job.kind}: {len(manifest['scenes'])} scenes, frames 0-{last_frame}/{total_frames - 1}, scale {params.scale}")

        _remotion_render(db, job, log, props, public_dir, silent, last_frame, params.scale)
        if job.id in _CANCEL:
            _update(db, job, status="cancelled", finished_at=_now())
            return

        _update(db, job, phase="muxing", progress=0.88)
        out = jdir / "output.mp4"
        video_sec = (last_frame + 1) / FPS
        narr_master = root / "_documentary" / f"project_{job.project_id}" / "narration" / "narration_master.wav"
        _mux(silent, narr_master, out, video_sec, params.normalize_audio, log)
        silent.unlink(missing_ok=True)

        _update(db, job, phase="validating", progress=0.95)
        expect = {"w": round(WIDTH * params.scale), "h": round(HEIGHT * params.scale)}
        report = quality_check(db, job.project_id, out, expect, video_sec, params.seconds is None, narr_master)
        _log(log, "QC: " + json.dumps(report, ensure_ascii=False))
        ok = not report["issues"]
        _update(
            db, job, status="succeeded" if ok else "failed", phase="done", progress=1.0, output_path=str(out) if out.is_file() else None,
            duration_sec=report.get("duration_sec"), qc=report, finished_at=_now(),
            error=None if ok else "Video không đạt kiểm tra: " + "; ".join(i["message"] for i in report["issues"][:4]),
        )
        if ok and job.kind == "final":
            from app.modules.documentary.service import DocumentaryService

            # A new final render supersedes any earlier final approval.
            DocumentaryService(db, library_root=root).bump_artifact(job.project_id, "render")


_PROGRESS = re.compile(r"Rendered (\d+)/(\d+)")
_BUNDLE = re.compile(r"Bundling (\d+)%")


def _remotion_render(db: Session, job: DocumentaryRenderJob, log, props: Path, public_dir: Path, out: Path, last_frame: int, scale: float) -> None:
    npx = shutil.which("npx")
    if not npx or not (REMOTION_DIR / "node_modules").is_dir():
        raise ValidationError("Chưa cài Remotion: chạy `npm install` trong thư mục remotion/.")
    # Remotion runs with its own working directory, so every path must be absolute: the app's
    # library dir is relative by default ("./data/library") and would resolve to nothing there.
    props, public_dir, out = props.resolve(), public_dir.resolve(), out.resolve()
    cmd = [
        npx, "remotion", "render", "src/index.ts", "Documentary", str(out), f"--props={props}", f"--public-dir={public_dir}",
        "--muted", f"--scale={scale}", f"--frames=0-{last_frame}", "--log=info",
    ]
    _update(db, job, phase="bundling", progress=0.04)
    proc = subprocess.Popen(
        cmd, cwd=REMOTION_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
    )
    _PROCS[job.id] = proc
    started = time.monotonic()
    last_pct = -1
    for line in proc.stdout:  # type: ignore[union-attr]
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line).rstrip()
        _log(log, clean)
        if job.id in _CANCEL:
            proc.kill()
            break
        if time.monotonic() - started > RENDER_TIMEOUT_SEC:
            proc.kill()
            raise ValidationError("Render quá thời gian cho phép.")
        m = _PROGRESS.search(clean)
        if m:
            frac = int(m.group(1)) / max(int(m.group(2)), 1)
            pct = int(frac * 100)
            if pct != last_pct:
                last_pct = pct
                _update(db, job, phase="rendering", progress=round(0.1 + 0.76 * frac, 3))
            continue
        b = _BUNDLE.search(clean)
        if b:
            _update(db, job, progress=round(0.02 + 0.08 * int(b.group(1)) / 100, 3))
    code = proc.wait()
    if job.id in _CANCEL:
        return
    if code != 0 or not out.is_file():
        raise ValidationError(f"Remotion thoát với mã {code} — xem log render.")


def _mux(video: Path, audio: Path, out: Path, video_sec: float, normalize: bool, log) -> None:
    if not audio.is_file():
        raise ValidationError("Không thấy narration master để ghép tiếng.")
    af = ("loudnorm=I=-16:TP=-1.5:LRA=11," if normalize else "") + "apad"
    # loudnorm upsamples internally, so the output rate/channels are pinned explicitly (-ar/-ac).
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", af, "-ar", "48000", "-ac", "2", "-t", f"{video_sec:.3f}", "-movflags", "+faststart", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800)
    _log(log, f"ffmpeg mux exit {r.returncode} {r.stderr.strip()[-300:]}")
    if r.returncode != 0 or not out.is_file():
        raise ValidationError(f"Ghép audio thất bại: {r.stderr.strip()[-300:]}")


# =====================================================================================
# Quality check
# =====================================================================================
def _probe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


def _black_intervals(path: Path) -> list[tuple[float, float]]:
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf", f"blackdetect=d={BLACK_MIN_SEC}:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=1800,
    )
    return [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)", r.stderr)
    ]


def quality_check(db: Session, project_id: int, video: Path, expect: dict, video_sec: float, full_length: bool, master: Path) -> dict:
    """Checks the finished file and names the scene responsible for each problem."""
    issues: list[dict] = []
    warnings: list[dict] = []
    info = _probe(video)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration", 0) or 0)
    if v is None:
        issues.append({"code": "no_video", "message": "File không có luồng video."})
    else:
        if (v.get("width"), v.get("height")) != (expect["w"], expect["h"]):
            issues.append({"code": "bad_resolution", "message": f"Độ phân giải {v.get('width')}×{v.get('height')}, cần {expect['w']}×{expect['h']}."})
        num, _, den = str(v.get("r_frame_rate", "0/1")).partition("/")
        fps = float(num) / float(den or 1) if num else 0.0
        if abs(fps - FPS) > 0.01:
            issues.append({"code": "bad_fps", "message": f"Tốc độ khung {fps:.2f} fps, cần {FPS}."})
    if a is None:
        issues.append({"code": "no_audio", "message": "File không có luồng âm thanh."})
    elif int(a.get("sample_rate", 0) or 0) != 48000:
        # A first real render came out at 96 kHz (loudnorm upsampling): playable, but not the standard.
        warnings.append({"code": "audio_sample_rate", "message": f"Âm thanh {a.get('sample_rate')} Hz, chuẩn là 48000 Hz."})
    if abs(duration - video_sec) > DURATION_TOL_SEC:
        issues.append({"code": "bad_duration", "message": f"Thời lượng {duration:.2f}s, mong đợi {video_sec:.2f}s."})
    if full_length and master.is_file():
        try:
            m = media.probe_duration(master)
            if m > duration + 0.05:
                issues.append({"code": "audio_cut_off", "message": f"Video ({duration:.2f}s) ngắn hơn narration ({m:.2f}s) — lời dẫn bị cắt."})
        except ValidationError:
            pass

    timings = list(
        db.scalars(select(DocumentarySceneTiming).where(DocumentarySceneTiming.project_id == project_id).order_by(DocumentarySceneTiming.order_index))
    )

    def scene_at(t: float) -> str:
        for tm in timings:
            if tm.start - 0.01 <= t < tm.end + 0.01:
                return tm.scene_key
        return "?"

    blacks = _black_intervals(video)
    for s, e in blacks:
        issues.append(
            {"code": "black_frames", "scene": scene_at(s), "start": s, "end": e,
             "message": f"Cảnh {scene_at(s)}: có khung hình đen từ {s:.2f}s đến {e:.2f}s."}
        )
    for tm in timings:
        if tm.needs_review:
            warnings.append({"code": "timing_unverified", "scene": tm.scene_key, "message": f"Cảnh {tm.scene_key}: timing {'ƯỚC LƯỢNG (không có timestamp thật)' if tm.source == 'estimated' else 'khớp từ thấp'} — chưa xác nhận chính xác."})
    return {
        "ok": not issues, "issues": issues, "warnings": warnings, "duration_sec": duration,
        "width": v.get("width") if v else None, "height": v.get("height") if v else None,
        "has_audio": a is not None, "audio_sample_rate": int(a.get("sample_rate", 0) or 0) if a else None, "black_intervals": len(blacks),
    }
