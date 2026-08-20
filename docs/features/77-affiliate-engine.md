# 77. Affiliate Engine

**Commit:** `pending`

Pipeline: Content → Audience → Product Category → Product → Affiliate
Link → Click → Order → Commission.

## Reuse, not duplication

`PublishLog` already had `affiliate_product` (free text)/`affiliate_clicks`/
`affiliate_sales`/`affiliate_revenue` (manually entered, real "Order"/
"Commission" data -- no generic affiliate-network API exists to pull this
automatically, out of scope to build one). This task adds exactly one
bare int, `PublishLog.affiliate_link_id` (no FK/import, same convention
as its own existing `ai_story_job_id`), to optionally attribute a
publish's *existing* affiliate_sales/affiliate_revenue to a specific
tracked link -- never a second, duplicate set of sales/revenue columns.
`ContentIdea.commercial_intent` (content_strategy) already anticipated
this task by name in its own docstring; left untouched -- see
app/modules/affiliate/models.py's own docstring for why forcing it into
a rigid enum now would require a forbidden cross-module import, and why
the real "commercial or organic, configurable" switch lives on
`PublishLog.affiliate_link_id` instead (null = organic, set = commercial,
always a human decision).

## New module: `app/modules/affiliate/`

Repository → Service → API, mirroring `content_strategy`'s exact split:

- `models.py` -- `AffiliateProduct` (name/category/tags/price/
  commission_rate/affiliate_url/platform/rating/review_count/active/
  product_score, per this task's own field list) and `AffiliateLink`
  (real, atomically-incremented `click_count`).
- `repository.py` / `service.py` -- CRUD + validation (commission_rate
  0-1, rating 0-5).
- `scoring.py` -- **deterministic** Product Score (same "no ML,
  transparent, hand-tunable" convention as Task 08/09): commission_rate,
  price-vs-category-peers, demand (real logged sales via linked
  PublishLog rows), and rating each contribute 0-1 components with fixed
  weights; a component with no supporting data is **excluded**, not
  zeroed, and remaining weights renormalize. "Return risk" (named in this
  task's own spec) has no data source anywhere in this app -- always
  excluded, never fabricated.
- `matching.py` -- category-recommendation prompt (AI, since "Female
  self-worth" → self-care/beauty/perfume has no keyword overlap a plain
  matcher could find) kept separate from `match_products()` (fully
  deterministic: `final_score = category_relevance × product_score`,
  same static-score × contextual-factor shape as Task 09's own weight
  formula). A product whose category/tags don't overlap any recommended
  category is never returned -- this task's own "do NOT inject products
  into every story."
- `router.py` -- Product/Link CRUD, `POST .../recompute-score`, and a
  **real** click-redirect (`GET /r/{code}`, mounted directly on the app,
  no `/api/v1` prefix, for a short shareable link). Real click counting
  only works once wherever the link is posted can reach this backend --
  for the default desktop-local deployment that's only true from the
  same machine; same category of constraint as Task 11's TikTok redirect
  URI. Disclosed in the UI, not silently assumed to "just work."

## Composition roots

- `app/api/v1/endpoints/affiliate_recommend.py` -- the only place
  importing `affiliate` + `ai.llm_client` (+ `content_strategy` to
  resolve a `content_idea_id`) together. `POST /affiliate/recommend-categories`
  and `POST /affiliate/recommend-products`, both **read-only/advisory** --
  neither writes anything or auto-attaches a product to a story/idea/
  publish; a human always creates the `AffiliateLink` and sets
  `PublishLog.affiliate_link_id` themselves.
- `app/api/v1/endpoints/affiliate_performance.py` -- KPIs
  (clicks/orders/GMV/commission/revenue-per-1,000-views/revenue-per-video),
  joining core `PublishLog` + `affiliate` + `app.services.insights` (real
  view counts). Clicks are split into `real_tracked_clicks` (from
  `AffiliateLink.click_count`) and `manual_clicks` (`PublishLog.
  affiliate_clicks` for rows with no structured link) so the two data
  qualities are never conflated. GMV only counts orders with a known
  linked product price; excluded orders are counted and disclosed, not
  dropped silently.

## Verification

Real, hand-checked math throughout an isolated backend+DB+frontend:
two products in the same category (`price_component`/`commission_component`/
`review_component` combined with renormalized weights) matched the API's
own computed `product_score` exactly (49.33 and 37.0). A real `GET /r/{code}`
redirect returned a genuine 302 to the product's `affiliate_url` and
incremented `click_count` 3 times atomically; an unknown code 404s. A
`PublishLog` linked to that link (2 sales, $15.50 revenue) plus a second,
manual/unlinked log (5 manual clicks) produced KPI totals matching hand
calculations exactly (8 clicks split 3 real/5 manual, GMV $80 = 2 × $40,
commission $15.50, revenue/video $15.50 across 1 commercially-active
video). A real AI call for `story_text="Female self-worth"` initially
returned long descriptive category phrases that didn't match the catalog
-- caught during verification and fixed by tightening the prompt to
require short, canonical labels (1-3 words) plus adding substring-
tolerant matching in `match_products()`; re-verified end to end,
returning `self-care`/`journals`/`books`/`beauty`/`gifts`/`perfume` (near
match to this task's own worked example) and correctly ranking both
self-care products by `category_relevance × product_score`. Real
Playwright screenshots of the full page (KPIs, links with live click
counts, recommendation results), zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean.
