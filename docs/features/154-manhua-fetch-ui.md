# 154 — Manhua recap: in-app "paste a link" fetch UI

**Commit:** `f790a42`

Every chapter download so far went through Claude running
`tools/manhua_recap/recap.py fetch` from the terminal -- a plain download
step that doesn't need an AI turn, just burns tokens. New `/manhua-fetch`
page: paste a chapter URL, name a folder, pick a chapter count, click
"Tải chương". A history table below lists past fetches (link, folder,
saved/skipped counts, or the error if one failed).

- `POST /manhua-recap/fetch` + `GET /manhua-recap/fetch-log`
  (`backend/app/api/v1/endpoints/manhua_recap.py`), logged to a new
  `manhua_fetch_log` table (migration `0008_manhua_fetch_log`).
- The actual fetch/site-parsing/filler-image-dedup logic (previously only
  in the CLI tool) moved to `backend/app/modules/manhua/fetch.py` so both
  entry points share one implementation. The CLI still works without the
  backend server running -- it imports the module directly, same as
  before, just relocated.
- Filler-image dedup cache moved with it, from
  `tools/manhua_recap/_common_hashes.json` to `backend/data/` (or
  `%LOCALAPPDATA%/AIContentLibrary/data` in a packaged build), so the CLI
  and the API share one cache regardless of which one downloads first.
- The new-table migration collided with `create_all()` on the real dev DB
  (already past revision 0007, so `sync_schema` ran `create_all()` *then*
  `alembic upgrade head` -- both tried to create the table). Fixed the
  same way the 0004-0007 column-add migrations guard themselves: check
  `sa.inspect(bind).get_table_names()` first and skip if it's already there.
