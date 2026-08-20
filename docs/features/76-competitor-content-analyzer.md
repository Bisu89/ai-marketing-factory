# 76. Competitor Content Analyzer

**Commit:** `53a0923`

## API capability audit (required first deliverable)

Researched TikTok's actual official developer products before designing
anything:

- **Login Kit (OAuth 2.0) + Display API** (`user.info.basic/profile/stats`,
  `video.list`): fully usable by a commercial app, but only for the
  *authenticated user's own account* -- profile, stats, and own video
  list with real public metrics (views/likes/comments/shares/duration).
- **Content Posting API**: publishes to the authenticated user's own
  account. Not relevant here.
- **oEmbed** (`tiktok.com/oembed?url=...`): public, unauthenticated,
  no app registration -- returns title/author/thumbnail for ONE given
  video URL. No engagement metrics, no discovery/search.
- **Research API**: the only official TikTok product that can return
  *any* public user's videos + engagement metrics, searchable by
  keyword/user/hashtag. Restricted to vetted academic researchers at
  qualifying institutions; its own terms explicitly forbid commercial
  use. This app does not qualify, and using it here would violate its
  terms even if access were somehow obtained.

**Conclusion:** own-account sync is fully buildable through official,
ToS-compliant means. Bulk competitor video/engagement data is **not**
available to a commercial app through any official TikTok channel --
scraping was ruled out by this task's own explicit instruction. Confirmed
this with the user before building anything (see conversation): the
Competitor side is manual-entry + oEmbed only (title/thumbnail/author
auto-filled for a URL the user pastes; the user types what they read
publicly, same as quoting an article -- never bulk/automated).

## Setup requirement (explicit, per this task's own instruction)

A TikTok Developer account + registered app (Client Key/Secret) is
required, plus an **HTTPS** Redirect URI the user registers with that
app -- TikTok does not accept `http://`/localhost redirect URIs, and a
new app is restricted to a manually-added sandbox test-user allowlist
until TikTok reviews and approves it for each scope, for real accounts.
This app cannot create, host, or approve that HTTPS endpoint or the app
review -- both are exposed as explicit config fields in Settings with
this constraint stated inline, not silently assumed away.

## Architecture

New `app/modules/competitor_intelligence/` (own tables, no FK into other
modules, per app/modules/README.md):

- `TikTokAccountLink` + `TikTokVideo` -- the user's own connected
  account (real OAuth tokens, plaintext columns -- same posture as this
  desktop-local app's existing `.env`-stored `anthropic_api_key`, not a
  new weaker stance) and its synced own videos (every metric column
  overwritten in full per sync, never a local counter).
- `CompetitorVideo` -- a competitor video manually submitted by the
  user, with 6 nullable abstract-pattern columns (emotional_pattern/
  hook_structure/conflict_type/character_type/ending_style/
  estimated_format) + reasoning, filled only by an explicit `/analyze`
  call. Never stores the original script/caption as "the analysis" --
  the AI schema only accepts the 6 abstract fields + reasoning (this
  task's own "Do NOT copy competitor scripts" instruction, enforced at
  the JSON-schema level, not just by prompt wording).
- `tiktok_client.py` -- thin `httpx` wrapper (already a project
  dependency) around TikTok's real v2 endpoints + PKCE. Every shape
  matches TikTok's own documented API but has **not** been exercised
  against a real, approved TikTok app (no such credentials exist in
  this environment) -- flagged here and in code comments.
- `service.py` -- pure module logic: OAuth state (in-memory, PKCE
  verifier keyed by `state`, same short-lived-coordination-dict shape as
  `asset.import_service`'s own `_CANCEL_EVENTS`), token refresh-with-
  margin, CompetitorVideo CRUD, and the prompt-build/response-parse pair
  for analysis.
- `sync_job.py` -- one-thread-per-run background sync (mirrors
  `asset.import_service`'s lightweight shape, not `DownloadEngine`'s
  persistent pool -- no external resource to serialize beyond simple
  rate limiting).
- `router.py` (module's own) -- OAuth start/callback, account get/
  disconnect, sync trigger, own video list, CompetitorVideo CRUD. Fully
  self-contained, no other module import needed.
- `app/api/v1/endpoints/competitor_analysis.py` (composition root) --
  the ONE endpoint needing `app.modules.ai.llm_client` alongside
  `competitor_intelligence`: `POST /competitor-videos/{id}/analyze`.
  Same "module builds the prompt, composition root calls
  `call_structured()`" split `content_generate.py`/`beat_generate.py`
  already use -- `competitor_intelligence/service.py` itself never
  imports `app.modules.ai`.
- AI cost for this feature is **not** covered by Task 10's
  `ai_generation_history` (its `video_id` is a NOT NULL FK to the core
  Library `video` table, which a competitor's video can never satisfy)
  -- `CompetitorVideo` carries its own provider/model/token columns
  instead. A real, disclosed gap, not silently folded into a table it
  doesn't fit.

## Feeding into Content Strategy

Confirmed with the user: read-only reference only, same treatment as
Task 09's Recommendations panel. A "Competitor Patterns" section on
Content Studio shows already-analyzed competitor patterns for the user
to read -- zero auto-fill/auto-injection into the Pillar/Format idea
generation below it. No backend coupling to `content_strategy` at all;
the panel is a pure frontend read of `competitor_intelligence`'s own
`GET /competitor-videos`.

## Settings

`tiktok_client_key`/`tiktok_client_secret`/`tiktok_redirect_uri` added to
`app/core/config.py`, same "plain field + dedicated `update_x()`
+ `.env`-persisted, never echoed back" shape as `anthropic_api_key`/
`openai_api_key`. Redirect URI is validated as HTTPS server-side.

## Verification

Real, live network calls throughout (no mocked happy path except the
one piece genuinely impossible to test -- see below):

- Real oEmbed call against a real, currently-live TikTok video
  (`@khaby.lame`) -- confirmed 200 + correct title/author/thumbnail
  parsing, and confirmed the "no data" path returns `None` (not an
  error) for an invalid video URL.
- Real end-to-end `POST /competitor-videos` -> real oEmbed enrichment ->
  real `POST /competitor-videos/{id}/analyze` using the user's own
  configured Anthropic key: the AI returned genuinely abstract patterns
  (e.g. "gây tò mò bằng một tình huống có vẻ hữu ích, chuyển sang cảm
  giác khó hiểu rồi kết thúc bằng sự hài hước") grounded in the
  submitted notes, with no verbatim script/dialogue reproduced.
- Real validation-error path: a CompetitorVideo with no title_caption/
  notes and a dead oEmbed lookup correctly 400s on `/analyze` instead of
  fabricating an analysis from nothing.
- Settings: HTTPS-only redirect URI validation, key/secret persistence
  and the "never echo back, only a presence boolean" contract all
  verified live.
- **Mocked boundary** (the one piece that cannot be tested for real --
  no TikTok Developer app credentials exist in this environment):
  `httpx.post` monkeypatched at the exact call site to return TikTok's
  own documented success/error token-exchange/refresh shapes, verifying
  parsing, error mapping to `ExternalServiceError`, and
  `service.get_valid_access_token`'s proactive-refresh-near-expiry and
  refresh-token-expired-forces-reconnect logic. This must be verified
  against a real sandbox TikTok app before depending on exact field
  names in production.
- Real Playwright screenshots: Competitor Analyzer page (Connect TikTok,
  add-competitor form, analyzed pattern card), Settings page's new
  TikTok section, and Content Studio's new read-only Competitor Patterns
  panel -- zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean.
