# 64. Content Strategy: Database Layer (Pillar → Format → Idea)

**Commit:** `pending`

Persistence-only layer for the future Content Strategy feature: a new
`app/modules/content_strategy/` module with `ContentPillar` →
`ContentFormat` → `ContentIdea` (models.py, schemas.py), no API endpoints,
no AI generation, no analytics -- per this task's own scope.

Pillar/Format names are plain DB rows, not a hardcoded Python enum, so they
stay user-manageable. `ContentIdea.target_emotion_id` is a bare FK into the
existing seeded `emotion` table (reused rather than duplicated), mirroring
`app.modules.scene_cutter.models.SceneCutJob.video_id`'s own bare-FK,
no-`relationship()` pattern. A starter set of 6 Pillars (Love, Marriage,
Family, Female Self-worth, Self-care, Lifestyle) is seeded idempotently in
`seed.py`, wired into `app/main.py` next to the existing
`seed_initial_data`. Formats were **not** seeded -- the task's format
examples (Betrayal, Mother Story, ...) were never mapped to a specific
Pillar, and a Format row requires a real `pillar_id`; guessing that mapping
would be inventing unspecified business data.

## Note: `story_job`/`story_version`

The task this module was built from says those tables "must remain the
source of truth for generated stories." They were in fact deleted from this
codebase immediately before this task (see
[63-remove-ai-content-and-insights.md](63-remove-ai-content-and-insights.md)),
at the same user's explicit request, in the same working session.
`ContentIdea` does not reference `story_job` and does not duplicate
generated-story storage either way, so this module doesn't depend on
whether/how story generation is rebuilt -- but whoever designs the next
stage (AI generation reading these Ideas) needs to decide what "the
generated story" is persisted as, since the table this brief assumed exists
does not.

## Verification

- `python -c "import app.main"` -- clean.
- Full app startup (`TestClient(app)`, real lifespan) against a temp SQLite
  DB: `content_pillar`/`content_format`/`content_idea` created with the
  expected columns and FKs (`content_format.pillar_id -> content_pillar`,
  `content_idea.pillar_id -> content_pillar`,
  `content_idea.format_id -> content_format`,
  `content_idea.target_emotion_id -> emotion`).
- Seeding confirmed idempotent: two consecutive startups against the same
  DB file leave exactly 6 pillar rows, no duplicates.
