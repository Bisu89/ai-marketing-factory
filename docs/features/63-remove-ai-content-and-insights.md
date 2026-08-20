# 63. Remove AI Content (Story/Hook/Caption) + Insights

**Commit:** `9e71326`

**Update (Task 04, see
[69-content-idea-story-hook-bridge.md](69-content-idea-story-hook-bridge.md)):**
`ai/story` and `ai/hook` (+ the shared `ai/history.py`) were restored --
a later task assumed they still existed, and the user chose to bring them
back rather than redesign around their absence. `ai/caption` remains
deleted.

**Update (Task 07, see
[72-performance-intelligence.md](72-performance-intelligence.md)):** the
Insights data layer below (`insight_upload`/`insight_post_snapshot`
models, CSV parser, `InsightService`, `/insights/*` endpoints, and
`PublishLog`'s link-to-post/unlink/views-interactions enrichment) was
also restored, for the same reason -- a later task needed it and the user
chose to bring it back. The frontend `/insights` page was deliberately
**not** restored (backend only, per that task's own scope). This note
exists so this file doesn't read as still-currently-true.

Removed two unused features at the user's request: the legacy AI Content
generator (`app/modules/ai/story|hook|caption`, `/ai` page) and the Insights
CSV-import/performance analytics subsystem (`app/services/insights/service.py`,
`performance_service.py`, `csv_parser.py`, `/insights` and `/performance`
endpoints, `insight_upload`/`insight_post_snapshot` tables, `/insights` page).
Neither was referenced by the Factory pipeline or Dashboard.

`PublishLog` (Library feature) stays -- it's still actively used
(`PublishLogSection.tsx` in the Library drawer) -- but lost the two things it
borrowed from the removed features: the "pick an AI Story version" dropdown
(now a plain manual `story_style` select) and the live views/interactions
lookup + link/unlink-to-post flow against `InsightPostSnapshot` (removed
outright, since without CSV upload there could never be a snapshot to link
to). `PublishLog.post_id`/`page_id` columns are left dormant on the model
(no migration framework to drop them) but no longer read or written anywhere.

`app/modules/ai/history.py` (`ai_generation_history`) was also removed --
it was written to exclusively by story/hook/caption's own services, so it
became dead code once those were deleted. `app/modules/ai/llm_client.py` and
`image_client.py` (used by the Factory pipeline's own content/image
generation) are untouched.

Verified: `python -c "import app.main"` succeeds; `npx tsc -b --noEmit`
clean.
