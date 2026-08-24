# 101. Settings: "New Template" Button

**Commit:** (pending)

Real user report: Settings' "Video Factory Templates" card could edit and
delete custom templates but had no way to create a new one — the only other
"create" path (VideoFactoryPage's "Save as Template") requires an
already-in-progress project.

## Root cause / scope

The backend already fully supported this (`POST /templates`, same request
shape as the existing `PUT /templates/{id}`) and the frontend already had a
working `createTemplate()` API call — just no UI entry point from Settings.
Pure frontend addition, no backend changes.

## What was added

`CreateTemplateModal.tsx`, mirroring `EditTemplateModal.tsx`'s exact narrow
edit surface (name/description/image style prompt/background music) since
no component exists anywhere that edits a full `ProjectConfig` (render/
motion/captions/watermark/etc.) to reuse wholesale. Adds one extra "Start
from" dropdown — blank (`SYSTEM_DEFAULT_PROJECT_CONFIG`) or a copy of any
existing template's full config — since starting from a known-good template
is more useful than always starting blank. Copies the source config
once, at creation time (not a live link), same snapshot semantics
`EditTemplateModal`/`Batch.template_id` already use elsewhere. A "New
Template" button was added to the template card's header in `SettingsPage.tsx`.

## Verification

`npx tsc -b --noEmit` clean. Real end-to-end verification via a headless-
Chromium driver script against the actual running app (no project skill or
`chromium-cli` was available in this session, so a small ad hoc Playwright
script was used instead, borrowing an already-installed `playwright`
package from a sibling project's `node_modules` via `NODE_PATH`): opened
Settings, clicked "New Template", picked "Copy of Emotional Story", filled
name/description, clicked Create — the new custom template appeared in the
list immediately with no console errors. Deleted the test template
afterward via the existing `DELETE /templates/{id}` endpoint.
