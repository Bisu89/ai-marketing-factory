# 106. Fix: Video Factory Looked Frozen After a Render Finished

**Commit:** `44b004f`

Real user report: "Video Factory sau khi gen video xong thì bị đứng luôn
phải f5 lại mới thấy kết quả" (after generating finishes, it just freezes,
have to refresh to see the result).

## Root cause

The render itself finished fine (Step 5 already showed the completed video
player). What silently got stuck was `ReadyToPostCard` -- the title/
description/thumbnail card shown once the Factory's own `PACKAGING` stage
(thumbnail candidates + optional AI metadata, a real billed LLM call) has
finished. Two compounding bugs in `ReadyToPostCard.tsx`:

1. It polled `GET /projects/{id}/package` on a fixed 2s cadence, but gave
   up entirely after a hard `POLL_TIMEOUT_MS` of 60 seconds. PACKAGING
   (6 thumbnail candidates by default, plus a real LLM call when
   "AI-write title/description/thumbnail text" is on) can easily take
   longer than a minute on a real machine.
2. While the package was incomplete -- both mid-wait and after giving up
   -- the component returned `null`: rendered literally nothing, no
   indication anything was happening. Once the 60s timeout passed with no
   visible sign polling had stopped, the page looked exactly like it had
   frozen, even though PACKAGING was still working fine in the background.
   Reloading the page (F5) remounted the component, resetting its internal
   timer, and by then PACKAGING had usually already finished -- which is
   why F5 "fixed" it.

## Fix

- Removed the hard polling cutoff -- the component now polls indefinitely
  while genuinely waiting.
- Added a visible "Preparing Title, Description & Thumbnail..." card
  instead of rendering nothing while waiting, switching to a "taking a bit
  longer than usual" hint after 20s so a slow run doesn't look abandoned.
- Distinguished "genuinely still working" from "will never complete":
  the component now also polls `getLatestFactoryRun` alongside the
  package and only shows/keeps polling for the preparing card while that
  run's own status is still active (`isActiveFactoryRun`, the same helper
  `ProductionProgress.tsx` already uses). Once the run reaches a terminal
  status (e.g. the render's output file went missing on disk --
  `generate_project_package`'s own documented "not an error" case -- or a
  plain manual/upload-based render with no FactoryRun at all), packaging
  has already been attempted and nothing further will happen automatically
  -- falls back to rendering nothing, the original, correct behavior for
  that case, instead of a permanent and misleading "still working" message.

## Verification

`npx tsc -b --noEmit` clean. Real browser check against the actual running
app on two real projects:
- A project whose FactoryRun is genuinely `COMPLETED` but whose render
  output file no longer exists on disk (found via direct DB inspection --
  `generate_project_package` correctly never produced a package for it):
  confirmed the card now correctly renders nothing (no false "still
  working" message), matching the original correct no-op behavior.
- Confirmed via the same script that the "Preparing..." card and its
  "taking longer than usual" text render correctly and persist past 20s
  when the gating condition is met, instead of ever going silent.
