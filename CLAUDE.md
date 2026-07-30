# AI Content Library

Desktop-local video content library (FastAPI + React/TypeScript + SQLite).
See `docs/README.md` for architecture, database schema, and a chronological
log of every feature built.

## Documentation

Whenever a feature is completed (a new endpoint, a new page, a new
background service, a schema change -- anything a user would notice or a
future contributor would need context on), add a new file under
`docs/features/`, numbered next in sequence (e.g. `10-...md`), and add one
line for it to the "Features" list in `docs/README.md`.

Each feature doc should cover, briefly:
- What it does and why (the actual problem it solves, not just a restatement of the code)
- The commit hash/message it landed in
- Key files touched
- Any non-obvious design decision and the reasoning behind it
- Real bugs caught during verification and how they were fixed, if any

Keep entries factual and grounded in what was actually built and verified --
not aspirational or speculative about what a feature might do later.
