# 110. AI Metadata: Default to On

**Commit:** _pending_

Real user request: after producing several real episodes with "AI-write
title, description & thumbnail text" checked every time, re-checking it
manually on every single video was pure friction for no real benefit --
the cost is small (~$0.01 or less per video) and the user always wants it.

## What changed

`NewVideoModal.tsx`: `aiMetadataEnabled` now defaults to `true` instead of
`false`. Still a flat default, not persisted across opens (same as
`autoProduce`) -- a user who wants it off for a specific video can still
uncheck it.

## Verification

`npx tsc -b --noEmit` clean. Real browser check: opened "New Video" and
confirmed the checkbox renders checked by default.
