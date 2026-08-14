# 42 — Content Quality Gate: Beat Quality + Visual Coverage Score

**Commit:** `e653dfe`

Before rendering, scores a project's BeatPlan across 6 dimensions
(narrative, pacing, visual, motion, audio, captions) and returns
READY / NEEDS_REVIEW / BLOCKED with stable issue codes and per-beat
`beat_id`s. Wired into both single-project render (`VideoFactoryPage`'s
"Production Check" modal) and batch "Render All" (BLOCKED items are
skipped, not enqueued; NEEDS_REVIEW items need an explicit "Render
Anyway"). All deterministic arithmetic — no ML/AI/embeddings.

## Key finding: Task 14 (AssetMatcher) still doesn't exist

Same gap already documented in `docs/features/41-local-asset-ingestion.md`.
Built a deterministic stand-in (`_compute_asset_confidence` in
`quality_gate.py`) reusing Task 15's own filename tokenizer against the
beat's `visual_hint` vs. the asset's tags/filename — not a real matcher.

## Non-obvious decisions

- **`app.modules.quality` is a pure contract/analyzer with zero
  cross-module imports** (mirrors `app.modules.composition`); the actual
  Beat/Asset resolution happens in the composition root
  `app/api/v1/endpoints/quality_gate.py`, which `batch_render.py` imports
  `run_quality_check` from directly.
- **READY requires score>=90 AND zero warnings**, not just a score
  threshold — a naive weighted average let one bad beat hide inside a
  6-dimension average and still score 99. Found live during manual
  verification (Scenario C), fixed, then re-verified.
- **Asset confidence never falls back to `narration`** when `visual_hint`
  is empty — narration is what's *said*, not what's *shown*; falling back
  made almost every ordinary beat register as low-confidence.
- **Blocking issues always override the score** (score=96 + missing asset
  → still BLOCKED) — confirmed live via manual verification.
- Batch gained a `NEEDS_REVIEW` item status (`BATCH_ITEM_STATUSES` now 10
  values) distinct from `SKIPPED`, so the UI can tell "quality gate flagged
  this" apart from "structurally not ready."

## Tests

60 new tests (40 analyzer, 15 quality_gate, 5 batch integration —
including the brief's own literal "10 projects: 6 READY/3 NEEDS_REVIEW/1
BLOCKED → 6 RenderJobs" scenario). Full suite: 551/551 passing. Frontend
`tsc --noEmit`: 0 errors.

## Manual verification (real, live dev server + Playwright)

All 4 required scenarios reproduced on a real project (id 11, 5 real
1080×1920 assets): (A) all assets well-matched → READY/100. (B) removed
one beat's asset → BLOCKED (`MISSING_VISUAL_ASSET`), confirmed via the
real UI that "Render Video" never fires a render request and shows no
"Render Anyway" button. (C) swapped one asset for a mismatched/low-res one
→ NEEDS_REVIEW/99 (`LOW_VISUAL_CONFIDENCE`), reproducing the exact
score-override bug fix above. (D) set one beat's duration to 30s vs. the
others' 2.5s → NEEDS_REVIEW/88, 5 `PACING_OUTLIER` warnings, pacing
dimension 20/100 — confirmed live through the real "Production Check"
modal (screenshot: score, per-dimension ✓/⚠, warning list, Render Anyway).

## Cost

$0 — pure Python arithmetic, no external calls.

## Architecture

No ML/embeddings/LLM/virality prediction anywhere; score is labeled
"Readiness Score," never "Virality Score." No second Beat/Asset/render
model. `app.modules.quality` imports nothing from `app.modules.beat` or
`app.modules.asset`; only the composition root does.

## Next task

Task 17 — Production Dashboard: Factory Control Center + Batch/Render
Monitoring.
