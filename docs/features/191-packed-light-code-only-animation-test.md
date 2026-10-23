# 191 — Packed Light code-only animation test (`PkCode`)

A ~42s test of how far pure code gets for character action, with no pictures and no image-to-video: SVG scenery, two cartoon puppets (dad, son) on the stickman engine's skeleton, and keyed poses + two-bone IK for every action. Three acts: (1) dad walks carrying a bucket, bends and sets it down, ties a tarp rope while the tarp rises, son cheers; (2) son walks, bends to pick up three branches, carries a growing load back; (3) son walks in, drops the load, kneels, strikes a match three times (flame, smoke), then props his chin to think. SFX are placed on the action frames; no voice.

Commit: `feat(remotion): PkCode, a code-only character-animation test for Packed Light`

Key files: `remotion/src/pk-ep01/{CodeAction,puppet,pk-moves,ik}.tsx|ts`, `remotion/src/Root.tsx`.

Decisions:
- `pk-moves.ts` is a small step sequencer (`walk`, `to`, `wait`, `wobble`, `mark`) where each step blends from the previous pose; named `mark`s give the frames that props, IK windows and SFX hang on, so changing a timing moves everything with it.
- Hands reach real targets (rope, bucket, branches, matchbox, cone) with the IK from `ik.ts` instead of hand-tuned arm angles.
- Walk stride speed is tuned to the move speed (8 px/frame dad, 6.4 son) to limit foot sliding; not measured.
- Scenery is deliberately flat vector so the test isolates character motion; swapping in clean AI background plates is the upgrade path (the AI pictures in `PkOpen` have the characters baked in, so they cannot be reused as plates).

Checked: tsc clean; stills of every action beat viewed. Not verified: smoothness and feel of the motion, since only still frames were reviewed.
