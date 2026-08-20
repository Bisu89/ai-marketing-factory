# 63. Remove AI Content (Story/Hook/Caption) + Insights

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
