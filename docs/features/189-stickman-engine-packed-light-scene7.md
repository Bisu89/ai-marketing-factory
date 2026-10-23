# 189 — Stickman vector engine + Packed Light scene 7 test

Forked the vector stickman engine from `stickman-video` into `remotion/src/stickman/` and added `remotion/src/pk-ep01/Scene7.tsx` (composition `PkScene7`): a ~56s test of the PACKED LIGHT knife/feather-stick scene with two seated figures. Goal: check that stick figures can act a father-son handover, not just stand in a diagram.

Commit: `feat(remotion): fork stickman engine, add Packed Light scene 7 test`

Key files: `remotion/src/stickman/*` (engine copy), `remotion/src/pk-ep01/Scene7.tsx`, `remotion/src/Root.tsx`, `remotion/package.json` (+`@remotion/google-fonts`, needed by `fx.tsx`).

Decisions:
- Separate fork on purpose: `stickman-video` stays the engine source/sandbox. Packed Light-specific code stays in `pk-ep01/` so `stickman/` can be re-synced by overwriting.
- `spiderman.tsx` and its `Hero` preset were removed from the fork (copyrighted character; not needed here). The fork therefore differs from the source in `cast.tsx`; keep that in mind when re-syncing.
- `moves.ts` has no hand-targeted moves, so `Scene7.tsx` solves arms with two-bone IK to land hands on the knife and stick. This is scene-local for now, not yet a shared move.

Caught while checking stills: the knife safety sweep hit the dad's head (he now leans away), and the hand-over point sat at face height (lowered to chest). Only still frames were reviewed, not the motion.
