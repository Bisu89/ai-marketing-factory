# 12 — Content Workflow (editable status/topic/emotion/tags/notes + search & filter)

**Commit:** `ec48719` "Epic 12: Content Workflow -- editable
status/topic/emotion/tags/notes + search & filter" (`c5ce98a` for the
`docs/database.md` update).

## What it does

Turns a Library video from "a file with some read-only metadata" into
something a person can actually curate: a content workflow status, a topic,
an emotional tone, freeform tags, and notes -- all editable directly in the
video detail drawer -- plus a real search box and filter bar to find videos
by any of them. Milestones 4/5/6 from the original Sprint V8 plan
([09-library-frontend-ui.md](09-library-frontend-ui.md) noted these as
explicitly deferred) landed here, framed by the user as a named epic.

## What was already there vs. what was missing

Search/filter/sort/pagination already existed as a fully-built backend API
(`GET /videos?search=&platform=&status=&category_id=&tag=&favorite=&duration=&resolution=&sort=`,
see [08-library-backend-api.md](08-library-backend-api.md)) and tags/notes
already existed as DB columns/endpoints -- none of it was wired into the
frontend. `VideoDetailDrawer` only ever *displayed* status/category/notes;
there was no search input, no filter sidebar, and no sort control anywhere
in `LibraryPage`. This feature is mostly "build the frontend for backend
that already existed" plus two genuinely new pieces: the status workflow
rename and the Emotion field.

## Status: content workflow, not download state

Old: `unused / processing / published / archived / deleted` (download-flow
flavored, left over from before the Library existed as its own concept).
New: `downloaded → ready → published → archived`, with `deleted` kept as a
soft-delete marker outside the visible workflow (unchanged: soft-delete
still just sets `status="deleted"`, see `VideoLibraryService.delete_video`).
No data migration was needed -- the `video` table was empty in this dev DB
at the time of the change.

## Topic = Category, relabeled

The user's spec called for "Topic," but the existing `Category` table
(Couple/Family/Military/Proposal/Transformation/Comedy/Other) already *is*
that concept -- confirmed with the user before building, since renaming a
working table for no functional reason would just be churn. Backend table/
column names stay `category`/`category_id` (schema, repository, service,
seed data all unchanged); only the UI-facing label changed to "Topic" in
`VideoDetailDrawer` and `LibraryFilters`. `docs/database.md` documents this
so a future reader isn't confused about where "Topic" lives in the schema.

## Emotion: new lookup table

Same shape as `Category` exactly: its own table (`app/models/emotion.py`),
seeded once (Vui, Cảm động, Hài hước, Buồn, Kịch tính, Trung tính), GET-only
endpoint (`GET /emotions`), no create/rename/delete API -- a fixed list
picked from a dropdown, not user-managed. `Video.emotion_id` is a nullable
FK, `Video.emotion_name` mirrors the existing `category_name`/`platform_name`
computed-property pattern.

## Editable `VideoDetailDrawer`

- **Status**: a `<select>` styled with the same `status-badge` color classes
  it already had for read-only display, so it still looks like a colored
  badge but is now interactive.
- **Topic / Emotion**: two `<select>` dropdowns side by side, populated from
  `GET /categories` / `GET /emotions`.
- **Tags**: existing tags render as removable chips (`×` button calling
  `DELETE /videos/{id}/tags/{tag_id}`); a text input + button adds one or
  more comma-separated names (`POST /videos/{id}/tags`).
- **Notes**: a textarea with local draft state and dirty-tracking -- a
  "Lưu ghi chú" button only appears once the draft differs from the saved
  value, avoiding a save-on-every-keystroke or a no-feedback auto-save.

All of these call `PUT /videos/{id}` (a single generic `onUpdate(patch)`
prop) or the tag endpoints, then invalidate the `["videos"]` TanStack Query
cache -- the same list/drawer re-render pattern already used for the
favorite toggle.

## Search & Filter

New `LibraryFilters` component: a debounced (300ms) search box plus a
filter row (platform, status, topic, emotion, duration bucket, resolution
bucket, a favorite-only checkbox, and a sort dropdown), all read from and
written to the URL via `useSearchParams` -- consistent with the existing
`view`/`page` URL-driven state in `LibraryPage`. Changing any filter clears
the current page back to 1. A "Xoá bộ lọc" button appears only when at
least one filter is active.

## API contract change: `VideoOut.tags`

Changed from `list[str]` to `list[{id, name}]`. Tag *removal* needs the
tag's id (`DELETE /videos/{id}/tags/{tag_id}`), which a bare name can't
provide -- the old shape only ever supported *displaying* tags, never
letting a user remove one. `Video.tag_names` (the property that produced
the old `list[str]` shape) was deleted as dead code once nothing referenced
it anymore. `VideoCard`, `VideoTable`, and `VideoDetailDrawer` all updated
to read `tag.name`/`tag.id` instead of a bare string.

## Simplification enabled by the API change

`VideoOut` already computed `category`/`emotion` as plain display strings
(mirroring the existing `platform` field's `Field(validation_alias=...)`
pattern), so `VideoCard`/`VideoGrid`/`VideoTable` no longer need a
`categories` prop threaded down just to build a `categoryNameById` lookup
map client-side -- they read `video.category`/`video.emotion` directly now.
`categories`/`emotions` are still fetched at the `LibraryPage` level, just
only passed to where they're actually needed (the filter bar and the
drawer's edit dropdowns).

## Verification

Real end-to-end tests against the actual backend and a real browser
(Playwright), not mocked:

- Imported real test videos via `POST /videos`, exercised the full edit
  surface through the UI: changed status via the dropdown, changed topic
  and emotion, added tags ("wedding, funny"), removed one, typed and saved
  notes -- confirmed each change persisted by re-reading the video from the
  API afterward, not just trusting the UI's own re-render.
- Search, platform filter, status filter, and sort were each verified by
  waiting for the actual matching network response and checking its
  `total`/`items`, not just eyeballing the DOM (a naive `waitForLoadState`
  a race with this app's other background polling, e.g. Video Composer's
  job list poll, and produced a false "filter didn't work" reading before
  this was tightened up).

**Bugs caught during verification** (both turned out to be tooling/
environment issues once isolated, not code bugs -- documented here because
tracking down which was which took real investigation):

1. Tag chips first rendered as bare `#` with no name, and removing one hit
   `DELETE /videos/2/tags/undefined`. Root cause: the backend's `--reload`
   dev server had gone stale again (a recurring issue on this Windows setup
   this project has hit before, see [10-scene-cutter.md](10-scene-cutter.md)'s
   verification notes) and was still serving the *old* `VideoOut.tags:
   list[str]` schema despite the source file already having the new
   `list[VideoTagOut]` shape. A clean process restart (not relying on
   `--reload`) fixed it immediately -- confirmed by re-curling the same
   endpoint before touching any app code.
2. A Playwright `.check()` call reported "Clicking the checkbox did not
   change its state" for the favorite-filter checkbox. Re-tested with
   `.click()` instead and it worked correctly (`false → true`, URL gained
   `favorite=true`) -- a Playwright API usage detail in the test script,
   not an app bug.
- All test videos/tags/notes removed afterward via hard-delete; Scene
  Cutter's and Video Composer's existing data were left untouched
  throughout (verified before and after).
