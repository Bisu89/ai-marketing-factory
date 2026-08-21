# 83. Video Factory: Template Badge + "Generate Full by AI"

**Commit:** `pending`

Real user report on the classic Video Factory page (`/video-factory`,
distinct from the Dashboard's quick "New Video" modal): (1) after
picking a Template, nothing showed which one was applied anywhere near
the top of the page; (2) this page had no "Generate Full by AI" like the
Dashboard's modal.

## Template indicator

`projectConfig.template_id` was already real, persisted state (survives
save/reload, per `buildProjectConfigForSave`/`getProject`) -- the only
place it was ever shown was a small `(from X)` note buried on Step 4
("Project defaults"), easy to miss right after picking a template on
Step 1. Added a `.vf-template-badge` next to the existing duration badge
in the page header (`VideoFactoryPage.tsx`), visible on every step,
reusing the `templateNameById` lookup that already existed.

## "Generate Full by AI"

Investigated first whether this page's flow was a different architecture
from the Dashboard's `Project`/`FactoryRun`-driven one -- it isn't:
`VideoFactoryPage.tsx` already loads/edits real Projects via `getProject`
(`?project=<id>`) and already renders the same `ProductionProgress`
(FactoryRun) component the Dashboard flow drives. What was missing was
only the *creation* call -- nothing on this page called `createProject`/
`startFactoryRun`.

Rather than build a second, parallel creation flow, this page now
imports and reuses `NewVideoModal` (the exact same component the
Dashboard uses) behind a new "Generate Full by AI" header button --
full parity (Template, Content language, Idea, Script, Produce
automatically, and the AI-image-per-beat generation button) with zero
duplicated logic. It navigates to `/video-factory?project=<id>` on
success, which this page's own existing `projectId`-driven load path
already handles regardless of whether that happens to be the page
already showing. The pre-existing "New Video" button (the classic
local-draft/`TemplatePickerModal` flow, `beats.json`-only, no real
Project until Save) is untouched -- both entry points coexist.

## Verification

Real Playwright run against an isolated backend+DB+frontend: created a
real Project via `POST /projects` with `template_id="emotional_story"`,
loaded it at `/video-factory?project=<id>`, confirmed the "EMOTIONAL
STORY" badge renders in the header; clicked "Generate Full by AI" and
confirmed the full `NewVideoModal` (Template/Content language/Idea/
Script/Produce automatically/Generate Full by AI) opens correctly on
this page. Zero console errors. `npx tsc -b --noEmit` clean.
