# 127 — YouTube Publishing: connect channels → auto-upload finished videos

**Commit:** _(fill in after commit)_

Managing several channels with manual uploads is the last big time sink.
This connects one or more YouTube channels via Google OAuth and uploads a
finished Factory video (`final.mp4` + `metadata.json` title/description/
hashtags + `thumbnail.jpg`) to a chosen channel, on a background thread.

## What it does NOT solve (a hard YouTube limitation, surfaced in the UI)

- **Un-audited OAuth project → every upload is locked to `private`** by
  YouTube regardless of the requested privacy. The user flips it to public
  in YouTube Studio. Requesting `public`/scheduled works once the user's
  own OAuth app passes Google's verification.
- **Consent screen in "Testing" → refresh tokens expire after 7 days** →
  the channel must be re-connected weekly. Verifying the OAuth app fixes
  this too.
- Default quota is ~6 uploads/day per Cloud project (`videos.insert` costs
  1600 of 10000 units).

The feature still removes the file-transfer + metadata typing + thumbnail
upload for every video — the tedious part.

## New module: `app/modules/publishing/`

Own two tables (`YouTubeChannel`, `YouTubeUploadJob`), no FK into any
other module (`YouTubeUploadJob.project_id`/`render_job_id` are bare ints,
same shape as `news`/`content_batch`). `youtube_client.py` is a pure httpx
wrapper around Google OAuth 2.0 + the YouTube Data API v3 resumable-upload
+ thumbnails.set endpoints — **httpx only, no `google-api-python-client`**,
matching `competitor_intelligence.tiktok_client`'s own "wrap one external
API, don't add a vendor SDK" convention. `service.py` is `SessionLocal`-
per-call (channel CRUD + OAuth-state + on-demand access-token refresh with
a 120s margin) plus `reconcile_uploads_on_startup()` (an upload left
`uploading` by a crashed process → `interrupted`, never auto-retried).

## Composition root: `app/api/v1/endpoints/publish_video.py`

The one place allowed to import `publishing` + `beat` (Project →
render_job_id) + `video_composer` (VideoComposeJob → output_path). Resolves
a project's completed render, reads the sibling `metadata.json`, creates a
`YouTubeUploadJob`, and runs the upload on a per-job daemon thread (uploads
are infrequent and independent — no shared queue, same lightweight pattern
as `batch_render.py`'s "Generate Beats"). Idempotent per (channel,
project); an explicit `retry` re-runs a failed/interrupted job.
`thumbnails.set` failure never fails the upload (the video is already up).

## Config + Settings

`google_oauth_client_id` / `google_oauth_client_secret` /
`youtube_redirect_uri` (`config.py`, same "plain str + `update_x()`" shape
as the TikTok creds). `PUT /settings/google-oauth-client` +
`/settings/youtube-redirect-uri`; `GET /settings` exposes
`has_google_oauth_client` + `youtube_redirect_uri` (never the secret). The
user creates the OAuth "Desktop app" client themselves (Cloud project,
YouTube Data API v3 enabled) — the app can't provision one.

## Frontend

New `/publishing` page (connect channel via the Google consent screen in a
new tab, enable/disable, disconnect, upload queue with retry + polling
while active). "Đăng lên YouTube" button in the Produced-Videos drawer
(channel + privacy picker → queues the upload). Settings gains a "YouTube
Publishing (Google OAuth)" card with the read-only redirect URI to paste
into Google Console. Sidebar item "Publishing".

## Verification

`pytest tests/modules/publishing tests/api/test_publish_video.py` (13):
channel connect (new + reconnect + missing-refresh-token rejection), token
reuse vs refresh-and-persist, upload job lifecycle, metadata/thumbnail
passthrough, duplicate-upload rejection, unrendered-project rejection,
failure landing on the job row, startup reconcile. `npx tsc -b --noEmit`
clean. Not run against a real Google OAuth project (no credentials in this
env) — the httpx shapes match Google's published docs, flagged here the
same way `tiktok_client` flags its own.
