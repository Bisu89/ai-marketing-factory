# 06 — Extensibility: EventBus + `app/modules/` convention

**Commit:** `365a019` (same commit as [05](05-database-normalization.md))

## What it does

Establishes how future content-generation modules -- Subtitle Generator,
Story Generator, Caption Generator, Voice Generator, Affiliate Matcher,
Analytics -- will plug in **without** the core (Video/Channel/DownloadEngine)
ever importing or knowing about them, and without them coupling to each
other.

None of those six modules are built yet. This is only the seam.

## The mechanism

`app/core/events.py` — a tiny in-process pub/sub (`EventBus.subscribe` /
`.publish`). `DownloadEngine` publishes `"video.downloaded"` with
`{video_id, video_path}` once a download is organized into the library, with
zero knowledge of who (if anyone) is listening. A subscriber that raises is
logged and does not affect the download or other subscribers (verified with
a deliberately-broken test subscriber).

## The convention (`app/modules/README.md`)

- Each future module gets `app/modules/<name>/` with its own SQLAlchemy
  model(s) (FK to `video.id`, never a column added to `video` itself), own
  Pydantic schemas, own service logic, own `APIRouter`.
- Needs background processing? Build your own small queue+worker-thread,
  don't import/extend `DownloadEngine` -- a change to download logic
  shouldn't be able to break an unrelated generator.
- React to new videos via `event_bus.subscribe("video.downloaded", handler)`,
  registered in `main.py`'s `lifespan` (the one place that "knows" the module
  exists -- that composition-root wiring is normal, not the coupling this
  rule is about).
- Generated artifacts (subtitle.srt, story.txt, voice.mp3, ...) live next to
  the video: `library/<platform>/<channel_name>/<video_id>/`.
- Affiliate Matcher / Analytics don't fit the "one file per video" shape --
  they get their own tables (`affiliate_match`, `analytics_event`), still FK'd
  to `video.id` only.

## Wiring

`app/api/deps.py`'s `get_event_bus()` exposes it to endpoints if a future
module's router needs to publish/subscribe from request handlers;
`app/main.py`'s `lifespan` creates the single `EventBus` instance and passes
it into `DownloadEngine`.
