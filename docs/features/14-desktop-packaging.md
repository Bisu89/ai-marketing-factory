# 14 — Desktop packaging (sellable Windows installer)

**Commit:** `6ae40ee` "Package the app as a sellable no-admin Windows
installer".

## What it does and why

Turns the app from a developer workflow (`uvicorn --reload` + a separate
`npm run dev` Vite server, Python/Node.js installed, manual `.env` editing)
into a single Windows installer (`AIContentLibrarySetup.exe`) a customer
double-clicks: no admin prompt, no terminal, a real app window (not a browser
tab). This follows the user's decision to sell the app as a distributed
desktop product rather than host it as a website — see project memory
`project_distribution_model.md` for the reasoning (mainly legal/copyright
liability around centrally hosting downloaded platform video, plus the app
already being architected single-tenant/local-only throughout).

## Architecture

**Frontend served by the backend, no Node.js at runtime.** `npm run build`
produces `frontend/dist/`; `backend/app/main.py`'s `create_app()` mounts it
as the SPA root (`/assets` static mount + a catch-all `GET /{full_path:path}`
falling back to `index.html` for client-side routes like `/story` on a hard
refresh) — but only `if frontend_dir.exists()`. In dev, that folder doesn't
exist, so this is a no-op and `npm run dev` on :5173 works exactly as
before. Registered last in `create_app()` so it never shadows `/api/v1/*` or
`/media/*` (Starlette matches routes in registration order).

**Config paths move to `%LOCALAPPDATA%` only when frozen.**
`app/core/config.py` gained `IS_FROZEN = getattr(sys, "frozen", False)`
(PyInstaller sets this) and `Field(default_factory=...)` for
`database_url`/`download_dir`/`library_dir`: frozen → default under
`%LOCALAPPDATA%\AIContentLibrary\data\...`; not frozen → the exact same
`./data/...` relative defaults as always. The `.env` file itself moves the
same way (`ENV_FILE_PATH`), so `update_library_dir()`/
`update_anthropic_api_key()` keep working unchanged either way. A new
`resource_path()` helper resolves bundled read-only assets (`frontend/dist`,
`resources/ffmpeg`) via `sys._MEIPASS` when frozen, or the repo layout in dev.

**Bundled ffmpeg, fixed at one call site.** `resources/ffmpeg/` ships
`ffmpeg.exe`/`ffprobe.exe` (see licensing note below). At the top of
`create_app()`, `_prepend_bundled_ffmpeg_to_path()` prepends that folder to
`os.environ["PATH"]` if it exists. This single change is what makes **both**
`video_composer/service.py`'s direct `subprocess.run(["ffmpeg", ...])` calls
**and** PySceneDetect's own internal ffmpeg invocation (inside
`scene_cutter/service.py`'s `split_video_ffmpeg()`) resolve to the bundled
binary — neither module needed to change, since both already just call
`"ffmpeg"`/`"ffprobe"` by bare name and rely on PATH.

**App shell: `backend/launcher.py`, run via `pywebview`.** Finds a free port
(`socket.bind(("127.0.0.1", 0))`), runs the existing FastAPI `app` via
`uvicorn.Server` in a background thread (not the blocking `uvicorn.run()`),
polls `/api/v1/health` until ready, then opens
`webview.create_window("AI Content Library", f"http://127.0.0.1:{port}/")`.
On window close, sets `server.should_exit = True` so the existing FastAPI
`lifespan` shutdown path runs — `DownloadEngine`/`SceneCutterService`/
`VideoComposerService` all stop their worker threads cleanly, nothing new
needed there. `launcher.py` is PyInstaller's entry point; the dev workflow
never touches this file.

**PyInstaller: onedir build** (`backend/AIContentLibrary.spec`) — chosen over
onefile to avoid onefile's per-launch temp-extraction delay. Bundles
`frontend/dist/`, `resources/ffmpeg/`, and certifi's `cacert.pem` (frozen
`httpx`/`anthropic` TLS needs this explicit) as `datas`; a handful of
`hiddenimports` for uvicorn's dynamically-selected loop/protocol modules,
pywebview's Windows backend, and SQLAlchemy's sqlite dialect. In practice the
frozen build worked on the **first run** with no missing-import iteration
needed — PyInstaller's community hook for `yt-dlp` in particular pulled in a
large, correct set of hidden imports (`websockets`, `mutagen`, `brotli`,
`Cryptodome`, etc.) automatically.

**Inno Setup: the actual installer** (`installer/installer.iss`).
`PrivilegesRequired=lowest` + `DefaultDirName={localappdata}\Programs\AI
Content Library` — installs into the user's own profile, never prompts for
admin/UAC. Packages the PyInstaller onedir output, creates a Start Menu
shortcut (+ optional desktop icon), and Inno Setup's standard uninstaller.
Because the app's own data lives under a *different* `%LOCALAPPDATA%`
subfolder (`AIContentLibrary`, not `Programs\AI Content Library`),
uninstalling removes only the installed program — a customer's videos/
database are untouched, matching normal Windows app conventions.

**`build_installer.ps1`** ties it together: fetch ffmpeg → `npm run build` →
`pyinstaller` → `ISCC installer.iss`. Needs to be re-run periodically
regardless of any other app change, since yt-dlp's extraction logic goes
stale as platforms change.

## ffmpeg licensing: GPL, not LGPL — and why that wasn't optional

`resources/download_ffmpeg.ps1` fetches BtbN's static Windows build. The
**GPL** variant was required, not a preference: Video Composer's merge step
calls ffmpeg with `-c:v libx264` (`video_composer/service.py`), and
`libx264`/`libx265` are GPL-only codecs that BtbN's **LGPL** build excludes
entirely (confirmed by actually downloading the LGPL build first and finding
`--disable-libx264 --disable-libx265` in its own reported configuration) —
the LGPL build cannot run this app's own Video Composer feature. Bundling a
GPL binary alongside a closed-source app via subprocess (not static linking)
is common commercial practice, but is a real legal question the app's owner
should get their own advice on before shipping commercially — not something
settled by this script or by me. `resources/ffmpeg/LICENSE.txt` (fetched
alongside the binaries, gitignored like the binaries themselves) must ship
with every build.

## Known limitations (not solved in this pass)

- **yt-dlp will go stale.** No auto-update mechanism for the app itself —
  when YouTube/TikTok change enough to break downloads, customers need a
  newer installer build.
- **License-key/activation is explicitly out of scope** — the user chose
  packaging over licensing as the first step.
- Windows only (matches the app's existing Windows-gated code — `tkinter`
  folder picker, `os.startfile`).
- Only Scene Cutter was exercised against the bundled ffmpeg live (see
  Verification) — Video Composer's ffmpeg calls go through the exact same
  subprocess+PATH mechanism, so this is inference from a shared code path,
  not a second independent live test.

## Key files

- `backend/app/core/config.py` — `IS_FROZEN`, frozen-vs-dev path defaults,
  `resource_path()`
- `backend/app/main.py` — `_prepend_bundled_ffmpeg_to_path()`, SPA static
  mount + catch-all
- `backend/launcher.py` (new) — pywebview entry point
- `backend/AIContentLibrary.spec` (new) — PyInstaller build spec
- `backend/requirements-build.txt` (new) — build-only tooling (PyInstaller),
  kept out of the runtime `requirements.txt`
- `installer/installer.iss` (new) — Inno Setup script
- `resources/download_ffmpeg.ps1` (new) — fetches bundled ffmpeg/ffprobe
  (binaries themselves gitignored, ~280MB, re-fetched per build)
- `build_installer.ps1` (new) — one-command repeatable build
- `frontend/.env.production` (new) — `VITE_API_BASE_URL=/api/v1` (relative,
  since the packaged app's port is dynamic); doesn't affect `npm run dev`
- `.gitignore` — added packaging build-artifact paths

## Verification

All performed against a real build on this machine, not simulated:

- `npm run build` → confirmed `frontend/dist/index.html` + assets exist;
  restarted the **dev** backend afterward and confirmed `/` now serves the
  SPA, `/story` (a client-side route) correctly falls back to `index.html`,
  a static asset serves at `/assets/...`, and `/api/v1/*` is untouched —
  proving the static-mount code itself works, before even freezing anything.
- Ran `launcher.py` directly (unfrozen) first: dynamic port selection,
  `uvicorn.Server` in a thread, the readiness poll, and `webview` opening a
  real window that made a real `GET /` request all worked on the first try.
- PyInstaller build (`backend/AIContentLibrary.spec`) succeeded with no
  missing-import iteration needed. Ran the frozen `.exe` directly: app
  window opened, SPA loaded, `/api/v1/settings` confirmed
  `library_dir`/`download_dir` resolved to
  `C:\Users\...\AppData\Local\AIContentLibrary\data\...` and a real
  `library.db` was created there.
- **Bundled-ffmpeg fix, verified rigorously, not just "it happened to
  work":** this machine already has an unrelated, manually-installed system
  ffmpeg on `PATH`. Relaunched the frozen exe with that system ffmpeg's
  directory explicitly stripped from its inherited `PATH` (so only the
  bundled binary could possibly succeed), then submitted a real Scene Cutter
  job (`POST /scene-jobs` against a genuinely two-scene test video generated
  with the bundled ffmpeg itself) — it completed successfully
  (`scene_count: 2`, correct split at the 3s boundary), proving
  `_prepend_bundled_ffmpeg_to_path()` is what PySceneDetect's internal
  ffmpeg call actually used.
- Compiled `installer.iss` with Inno Setup 6 (installed via
  `winget install JRSoftware.InnoSetup`, itself a no-admin per-user install)
  → `AIContentLibrarySetup.exe`, ~148MB. Ran it `/VERYSILENT
  /SUPPRESSMSGBOXES`: exit code 0, **no UAC/admin prompt**, installed to
  `%LOCALAPPDATA%\Programs\AI Content Library`, created a Start Menu
  shortcut. Launched the installed `.exe` directly from that location and
  confirmed it started correctly (same health/SPA checks as the direct
  frozen-build test). Ran the generated `unins000.exe` silently: confirmed
  the install folder and Start Menu shortcut were both removed cleanly.
- Confirmed `frontend/.env.production` does **not** leak into `npm run dev`
  — checked the dev server's own `import.meta.env` output showed
  `MODE: "development"` and the absolute `http://127.0.0.1:8000/api/v1`
  fallback, not the packaged build's relative `/api/v1`.
- All test artifacts (test videos, the frozen app's `%LOCALAPPDATA%` test
  data, the installed test copy) were cleaned up afterward.
