# 121. Auto-Delete the Render Cache N Days After a Render Finishes

**Commit:** `_pending_`

Follow-up to [120](120-cleanup-generated-render-cache.md): the user didn't
want to remember to press "Clean Render Cache" — they wanted a finished
project's regenerable voice/motion/audio cache gone automatically a week
after it renders.

## What it adds

- `Settings.render_cache_retention_days` (env `APP_RENDER_CACHE_RETENTION_DAYS`,
  **0 = off**, the shipped default) + `PUT /settings/render-cache-retention`
  and a "Dọn dẹp bộ nhớ (render cache)" dropdown on the Settings page
  (Off / 3 / 7 / 14 / 30 days).
- `assets_cleanup.perform_cleanup(...)` — the feature-120 endpoint body
  extracted into a reusable core, now with an `older_than_days` age gate
  (`CleanupSkipped.too_recent` for finished-but-within-window projects).
  A COMPLETED render job with **no** `completed_at` timestamp is treated
  as too-recent (never guessed old).
- `sweep_stale_render_cache(settings)` — the automatic sweep: `voice_factory`
  + `motion_engine` only (never AI images), `delete_files=True`.
- `app/main.py` lifespan runs it once at startup, then a daemon thread
  (`threading.Event`-gated so shutdown is instant) re-runs it every 24h.

## Non-obvious decisions

- **Shipped default is 0 (off).** Auto-deleting user data on a timer
  shouldn't be a surprise for someone who just installed the app — it's
  opt-in per install. This user's `.env` is set to 7.
- **Startup + 24h, not a real scheduler.** A desktop app isn't a 24/7
  server; it's opened and closed regularly, so a startup sweep already
  catches almost everything, and the 24h loop just covers a machine left
  on for days.
- **AI images are never in the automatic sweep** — non-deterministic and
  billed; only the manual endpoint can opt into `ai_image_generator`.
- Imported music/media (`source="LOCAL_IMPORT"`) is never touched — the
  sweep only ever queries the pipeline's own generated `source` values.

## Key files

- `backend/app/api/v1/endpoints/assets_cleanup.py` — `perform_cleanup`, `sweep_stale_render_cache`, age gate
- `backend/app/core/config.py` — setting + `update_render_cache_retention_days`
- `backend/app/api/v1/endpoints/settings.py` — GET field + PUT endpoint
- `backend/app/main.py` — startup sweep + 24h daemon thread
- `frontend/src/pages/SettingsPage.tsx`, `api/settings.ts`, `types/settings.ts`

## Verification

`tests/api/test_assets_cleanup.py` grew to 13 (age gate, no-timestamp =
too-recent, sweep no-op when disabled, sweep cleans only old projects).
`pytest tests/api/test_assets_cleanup.py tests/api/test_settings.py
tests/modules/asset` green (122). `npx tsc -b --noEmit` clean. Not yet
run against the live app (needs a backend restart).
