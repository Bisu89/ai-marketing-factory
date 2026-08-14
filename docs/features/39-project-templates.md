# 39 — Project Templates + One-Click Production Presets

**Commit:** _(fill in after commit)_

## What it does

Adds 3 built-in templates (Emotional Story, Couple Story, Custom) and
custom "Save as Template" -- pure configuration (render profile, default
motion, caption style, audio defaults), never a second pipeline. Choosing
a template snapshots its config onto the current project; after that the
project's own copy is authoritative and independent of the template. Adds
a deterministic Beat override > Project default > System default
resolver for motion, and a "Quick Render" shortcut that still goes
through the exact same preflight → RenderJob → queue → worker pipeline as
every other render in this app.

## Key architectural finding: no multi-project system exists

Before writing any code, this task's own instruction to inspect the
architecture first turned up something the brief's language ("New
Project", "Project A", "Open project") assumes but this codebase doesn't
have: there is no multi-project store. `app/modules/beat/router.py`'s own
docstring says it plainly -- "only one BeatPlan is ever 'the' current
one." The whole Video Factory is a single-project desktop tool; "the
project" *is* the one `beats.json`. Building real multi-project
persistence would be a genuine architecture change this task's own §34
forbids ("do not redesign the application", "do not refactor unrelated
modules"). Adapted scope: `ProjectConfig` rides along on `BeatPlan` itself
(new `config` field, alongside a new `project_name` display label) rather
than a separate project entity; "New Video" resets the current session
(with a confirm() if there's unsaved work) instead of creating a second
project record. `docs/architecture.md`'s "Project templates" and
"existing project compatibility" acceptance criteria are read against
this reality throughout.

## Templates

All three are plain `ProjectConfig` snapshots -- see
`app/modules/beat/schemas.py`'s `BUILTIN_TEMPLATES`:

| | Emotional Story | Couple Story | Custom |
|---|---|---|---|
| Motion default | SLOW_PUSH_IN | SLOW_PUSH_IN | STATIC |
| Captions | **big_statement** | emotional | emotional |
| Music volume | 0.18 | 0.15 | 0.15 |
| Render profile | SOCIAL_VERTICAL | SOCIAL_VERTICAL | SOCIAL_VERTICAL |

**"BOLD captions" → `big_statement`**: this app's real caption preset set
is `emotional`/`cinematic`/`word_highlight`/`big_statement`/`quote` (see
`video_composer.models.CAPTION_PRESETS`) -- there is no literal "BOLD"
preset. `big_statement` (large, upper-cased, high-impact text) is the
closest real match to the brief's intent and is what's actually wired in;
noted here since the brief's own JSON examples use a name that doesn't
exist in this codebase.

## Configuration resolution

```
System defaults (ProjectConfig(), motion=STATIC)
      ↓
Template defaults (BUILTIN_TEMPLATES / a saved custom template)
      ↓
Project overrides (BeatPlan.config -- an independent deep copy after "Use Template")
      ↓
Beat overrides (Beat.motion_preset, now nullable -- None = inherit)
      ↓
Effective configuration
```

One resolver on each side, not spread across UI components:
`effective_motion_preset()` (`beat/schemas.py`) and
`effectiveMotionPreset()` (`types/videoFactory.ts`) -- identical logic,
duplicated across the Python/TS boundary per this codebase's established
convention. `Beat.motion_preset` changed from a hardcoded `STATIC`
default to `BeatMotionPreset | None = None` to make "no explicit choice"
actually representable -- backward compatible by construction: an old
beats.json's explicit `"motion_preset": "STATIC"` still means STATIC
(only a genuinely absent/null field resolves through the project default
now), and `DEFAULT_PROJECT_CONFIG.motion.default_preset` is itself STATIC,
so an existing, template-less project's rendered look is byte-for-byte
unchanged. AI-generated beats (which never assigned a motion preset to
begin with) now correctly inherit the project's template default instead
of always landing on STATIC.

## Isolation & immutability

`Template.config` is copied (`JSON.parse(JSON.stringify(...))` client-side,
`model_copy(deep=True)` server-side), never referenced, at the moment a
template is applied -- proven by `TemplateIsolationTests` (mutating a
project's config, or creating two projects from the same template, never
touches the template). Built-in templates are Python constants with no
write path at all. Custom templates are id-namespaced against built-ins
(`save_custom_template`/`create_template` both reject reusing a built-in
id) so a custom template can never shadow one.

## Changed files

Backend: `app/modules/beat/schemas.py` (+`ProjectConfig` and its 4
sub-configs, +`Template`, +`BUILTIN_TEMPLATES`, +`effective_motion_preset`,
+`sanitize_project_config_for_template`, `Beat.motion_preset` now
nullable, `BeatPlan` +`project_name`/+`config`), `app/modules/beat/service.py`
(+custom template load/save/delete, mirrors `save_beats_json`'s own
convention), `app/modules/beat/router.py` (+`GET/POST/DELETE /templates`).

Frontend: `types/videoFactory.ts` (+`ProjectConfig`/`Template` types,
+`effectiveMotionPreset`, `motion_preset`/`motionPreset` now nullable),
`api/template.ts` (new), `pages/VideoFactoryPage.tsx`/`.css` (Choose
Template modal, "New Video"/"Quick Render" header actions, Project
defaults panel + Save as Template modal in Step 4, Production Mode +
cost display in Step 5), `pages/SettingsPage.tsx`/`.css` (Video Factory
Templates card, built-in vs. custom badges, delete for custom only).

## New Project flow

`New Video` (header) → confirm if there's unsaved work → `Choose
Template` modal (3 cards: name/description/profile/captions/motion/audio,
built-in badge) → `Use Template` snapshots the config and jumps to Step 1
(Script + Project name). An existing saved project (the common case) is
never interrupted -- the picker only auto-opens once, the very first time
this app has nothing saved at all.

## Quick Render

`handleQuickRender()` is exactly `setStep(5); await handleSubmitRender()`
-- the same function the manual "Render Video" button already calls,
which is the same `renderComposition()` → preflight → `VideoComposeJob`
(QUEUED) → the existing local worker queue built in Task 11. No second
pipeline, no bypassed validation -- literally a UI shortcut around
clicking through Steps 2-5 by hand.

## Tests

386 backend tests passing (up from 351 at task start): 28 new tests in
`tests/modules/beat/test_templates.py` (validation, application,
isolation, version, custom persistence, sanitization, backward
compatibility) + 7 new router tests in `tests/modules/beat/test_router.py`
(list/create/delete, duplicate-name uniquification, builtin-delete
rejection) + 4 existing `test_schemas.py` tests updated for the nullable
`motion_preset` semantics. Frontend type-checks clean
(`tsc --noEmit` exit 0, zero errors after the nullable-type ripple
through `WorkingBeat`/`GeneratedBeat`/`VisualsEditor`/`buildScene`).

## Manual verification (real, not simulated)

- Backward compatibility: `GET /beat-plan` against the real, pre-existing
  5-beat project (saved before this task, no `config` key, explicit
  per-beat `motion_preset` values from earlier tasks) loads with `config`
  defaulted and every existing beat's motion preserved exactly.
- `GET/POST/DELETE /templates` against the real running backend: 3
  built-ins returned; a custom template created, listed, and deleted;
  deleting a built-in correctly rejected (400) -- caught and fixed a real
  bug here (`delete_template` checked the wrong set first and returned
  404 instead of "cannot delete built-in" for a builtin id).
- Real browser (Playwright): existing project loads without the template
  picker auto-opening; `New Video` → confirm dialog → 3 template cards
  render exactly as designed; `Use Template` (Emotional Story) → Step 4
  visibly shows "Project defaults (from Emotional Story)", Default motion
  = Slow Push In, Caption style = Big statement, Music volume = 0.18 --
  all screenshotted. Zero console/page errors throughout. The live
  verification session never called Save, and the real persisted project
  was confirmed unchanged afterward.
- Real render driven by a template fetched from the live API (Couple
  Story: SLOW_PUSH_IN motion, emotional captions) through
  `POST /video-compose-jobs/from-composition`: completed, h264/aac,
  1080x1920, 3 beats.

## Cost

The Couple-Story-driven verification render used TTS narration (no local
narration assets assigned in that quick check), correctly reporting
`external_api_calls: 1`, `external_api_cost_estimate: null` -- honest
accounting, not an invented number. Every local-narration render in this
app (Tasks 10/11's benchmarks, unchanged by this task) reports
`external_api_calls: 0` / `$0`. Local-first remains the only implemented
production mode; the Step 5 "Production Mode" indicator shows External AI
explicitly as "coming soon", not a working toggle.

## Problems

None outstanding. One scope note: the brief's "BOLD" caption preset name
doesn't exist in this codebase's real preset set -- mapped to
`big_statement` (see "Templates" above), not invented.

## Architecture

One render pipeline (`render_composition` → `VideoComposerService`,
untouched by this task). One queue (Task 11's, reused by Quick Render
unchanged). One configuration system (`ProjectConfig`, shared by
templates and projects). No Redis/Celery/marketplace/module-to-module
imports were introduced -- `app/modules/beat` still imports only
`app.core` (specifically `app.core.render_profile` for profile
validation, the one core dependency every module already has).

## Next task

Task 13 — Production UX: Batch Video Creation + Script Queue.
