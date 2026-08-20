# 74. AI Content Learning Loop

**Commit:** `pending`

Transparent, explainable "what should we generate next?" recommendation
layer -- explicitly **not machine learning** (no model, no training, no
ML framework), per this task's own instruction. Built entirely on Task
08's `WinnerGroupStats`/`TrendGroupStats` -- no metric computed twice.

## The formula

Matches the task's own example exactly:

```
weight = historical_performance × sample_confidence × recency_factor
```

- `historical_performance` = Task 08's `performance_score` (already
  platform-normalized, not raw views) rescaled to 0-1.
- `sample_confidence` = Task 08's confidence tier
  (insufficient/low/medium/high) mapped to 0.0/0.5/0.75/1.0 --
  `insufficient` forces the group out of recommendations entirely (a
  recommendation is a stronger claim than a "winner" label, so it
  inherits Task 08's "never on 1-2 videos" rule at least as strictly).
- `recency_factor` = Task 08's trend classification (rising/stable/
  underperforming/insufficient_data) mapped to 1.2/1.0/0.7/0.85.

All three factors and the weighting table live in
`app/services/insights/recommendation_service.py`, in one place, plainly
readable -- no hidden coefficients.

## Dimensions

Pillar, Format, Hook (all reused from Task 08 directly) plus a new
**Emotion** dimension for this task's own "winning emotional patterns"
requirement -- traced via the same
`PublishLog.ai_story_job_id -> StoryJob.content_idea_id -> ContentIdea.target_emotion_id -> Emotion.name`
chain Task 07/08 already established for pillar/format (a fresh resolver
in the new composition root, `content_recommendations.py`, rather than
editing Task 07/08's own already-verified `_resolve_pillar_format`).

## Output

`GET /recommendations/content?limit=&min_sample_size=&dimension=` returns
one combined, cross-dimension, weight-sorted list (matching the task's
own example output mixing a format + a format + a pillar in one list),
each item carrying `reasons: list[str]` built directly from its own
numbers -- e.g. "Hiệu suất lịch sử ở mức khá (điểm hiệu suất 30.4/100)."
+ "Đủ mẫu để đánh giá: 6 video, độ tin cậy thấp." + "Xu hướng gần đây
đang tăng (+186.7%)." -- never a generic "AI recommends this."

## "Do not silently manipulate generation"

This endpoint is 100% read-only and is never called by any generation
endpoint (`POST /content-ideas`, `.../generate-story`, the batch flow) --
it only ever answers a question, never acts on it. The new "AI Content
Recommendations" panel on Content Studio is purely informational: no
auto-fill, no auto-trigger. The existing Pillar/Format dropdowns in the
"Tạo ý tưởng" section are completely unchanged -- the user reads the
recommendations, then makes their own choice, same as before this task.
A future task could wire an explicit, visible "use this suggestion"
button; not built here, to keep this pass unambiguous about who's in
control.

## Verification

Real weight-formula check by hand against a realistic dataset (2 formats
x 6 posts each -- one genuinely improving, one genuinely declining, plus
target emotions and hook types layered on): for "Betrayal"/"Love"/"Kịch
tính" (all resolving to the same 6 rising videos), computed
`historical_performance=0.3038, sample_confidence=0.5 (low, 6<10),
recency_factor=1.2 (rising)` → `weight = 0.3038 × 0.5 × 1.2 = 0.1823`,
**matching the API response exactly, digit for digit**. Same exact match
for the declining "Family"/"Mother Story"/"Cảm động" group (weight
0.0446) and the "Shock reveal" hook (weight 0.1716, combining the rising
Betrayal videos with 2 additional TikTok posts). `dimension=hook` filter
correctly narrows to just hook results; `min_sample_size=20` (above every
group's real sample size) correctly returns an empty list -- nothing
recommended on insufficient data, not a fabricated fallback. Real
Playwright browser run: the Content Studio page's new panel renders all
6 recommendations with correct labels/dimension badges/weights/reasons/
trend icons, and the existing Pillar/Format generation form below is
completely unaffected. Zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean.
Existing dev servers on 8000/5173 untouched.
