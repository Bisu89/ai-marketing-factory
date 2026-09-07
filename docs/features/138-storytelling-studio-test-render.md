# 138. AI Storytelling Studio — test render + first end-to-end produce

## End-to-end produce, verified

The story pipeline produced a real video for the first time: a 6-scene
imported story → `POST /produce` → compile → Factory (AI images → edge_tts
→ motion → audio → captions → render → package) → `video_hoan_chinh.mp4`,
1080×1920, 30.6 s, QA PASS 100. Total spend: **$0.036** (6 AI images);
everything else free. Timeline ~2 min (image gen 83 s dominates).

Two small fixes fell out of getting there:
- `sync_schema` crashed on an empty `alembic_version` table (feature 137).
- the pre-flight cost bar double-counted the planning LLM for an
  imported/planned story (feature 137 follow-up).
- a compiled story now defaults to **edge_tts**, not the robotic offline
  SAPI5 voice.

## Test render

`POST /stories/{id}/produce?test=true` — a fast, cheap look before
committing to the full story:

- compiles only the **first 5 scenes** into one throwaway `Project`
  (`"{title} — TEST"`), at the smaller **PREVIEW** profile (720×1280,
  24 fps) → ~3 AI images, ~$0.02, ~1 min
- never links to a chapter / episode and never advances `Story.status`, so
  a real Produce still compiles the whole thing fresh
- **not** blocked by the cost cap (its whole point is to be cheap)
- `GET /stories/{id}/compiled` now also surfaces the latest PRODUCE run's
  own projects (covers `single` compile mode too), each tagged `is_test`

Frontend: the Produce panel has a **"Test render (first 5 scenes)"**
button next to **"Produce full"**; a test entry shows with a 🧪 marker.

## Key files

`app/api/v1/endpoints/story_compile.py` (`test` param through
`compile_story` / `produce_story` / `_execute_story_produce_sync`,
`_build_beat_plan` render-profile override, `_compiled_view` now unions the
produce run's projects); `frontend` produce panel + `produceStory(id, test)`;
tests in `tests/api/test_story_compile.py`.

## Verification

12 compile tests (3 new: test uses first-N + PREVIEW + no chapter link;
test skips the cost guard; `_compiled_view` surfaces a test render) + 58
story-suite tests pass. `npx tsc -b --noEmit` clean; `npm run build`
succeeds. Live: a full produce rendered end-to-end (above); a
`?test=true` run against the same story compiled the first 5 scenes at
PREVIEW.

## Landed in

`2a13302`
