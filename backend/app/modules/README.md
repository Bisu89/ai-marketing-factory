# Future modules (Subtitle / Story / Caption / Voice / Affiliate / Analytics generators)

This folder is where each future content-generation module lives, one subfolder
per module: `app/modules/subtitle/`, `app/modules/story/`, `app/modules/caption/`,
`app/modules/voice/`, `app/modules/affiliate/`, `app/modules/analytics/`, etc.

The rule that keeps them from coupling to each other or to the download/library
core: **dependencies only point inward, never sideways, and the core never
points out.**

```
                 ┌─────────────────────────────────────────┐
                 │   Core domain (stable, already built)     │
                 │   Video, Channel, Playlist,                │
                 │   DownloadTask, DownloadHistory            │
                 │   app.core.events.EventBus                 │
                 └───────────────▲─────────────▲──────────────┘
                                 │             │
                     reads Video │             │ subscribes to
                     by id, FKs  │             │ "video.downloaded"
                     to video.id │             │ (or others, added
                                 │             │  as needed)
                 ┌───────────────┴──┐   ┌──────┴────────────┐
                 │ app/modules/       │   │ app/modules/       │   ... one per
                 │ subtitle/          │   │ story/             │       module
                 └────────────────────┘   └────────────────────┘
```

The core (`app/models/*`, `app/services/download`, `app/services/library`)
must **never** import anything from `app/modules/*`. A module may **never**
import another module. The only place that "knows" a given module exists is
the composition root (`app/main.py` for event subscriptions, `app/api/v1/router.py`
for mounting its API router) -- that wiring is unavoidable and fine; it is not
the coupling this rule is about.

## What a module owns

Each module is a fully self-contained vertical slice:

```
app/modules/subtitle/
├── models.py       # its own SQLAlchemy table(s), e.g. Subtitle(video_id FK, ...)
├── schemas.py       # its own Pydantic request/response shapes
├── service.py       # its own business logic (may run its own background
│                     #  worker thread/queue -- copy the pattern in
│                     #  app/services/download/engine.py, don't import it)
└── router.py        # its own APIRouter, mounted in app/api/v1/router.py
```

- **Its own table(s)**, never a new column bolted onto `video`/`channel`/etc.
  A module's model may have `video_id: Mapped[int] = mapped_column(ForeignKey("video.id"))`
  -- that FK direction (module -> core) is the only link allowed.
- **Its own background processing**, if it needs one (calling an LLM, a TTS
  API, etc. shouldn't block a request). Don't extend or import `DownloadEngine`
  -- build a small queue+worker-thread of your own following the same shape.
  Sharing the concrete class would mean a change to download logic could break
  an unrelated generator.
- **Its own artifact files**, stored next to the video it belongs to:
  `library/<platform>/<channel_name>/<video_id>/` already exists per video
  (see `app/services/library/organizer.py`) -- put `subtitle.srt`, `story.txt`,
  `captions.json`, `voice.mp3` etc. there, so everything for one video stays
  physically together.

## How a module finds out about new videos

Subscribe to `app.core.events.EventBus` instead of being called directly:

```python
# app/modules/subtitle/service.py
def on_video_downloaded(payload: dict) -> None:
    video_id = payload["video_id"]
    # enqueue your own background job here

# app/main.py, inside lifespan(), after event_bus is created:
from app.modules.subtitle.service import on_video_downloaded
event_bus.subscribe("video.downloaded", on_video_downloaded)
```

`DownloadEngine` publishes `"video.downloaded"` with `{"video_id", "video_path"}`
once a download completes and the file is organized into the library -- it has
no idea who (if anyone) is listening. A module that doesn't exist yet, or is
temporarily broken, can never break a download.

## Affiliate Matcher / Analytics specifically

These two don't hang a file off a single video the same way subtitles/captions
do:

- **Affiliate Matcher** likely produces N matches per video (a video ↔ product
  many-to-many) -- give it its own `affiliate_match` table (video_id FK,
  product info), not a single file.
- **Analytics** is aggregate/time-series by nature -- give it its own
  `analytics_event` table it appends to, and compute rollups from that. Do not
  add "view_count_today" style columns to `video`.

Same rule either way: own table(s), FK to `video.id`, no reverse dependency.
