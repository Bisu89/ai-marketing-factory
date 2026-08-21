# 84. Template Edit UI + Per-Template Image Style Prompt

**Commit:** (pending)

Real user report: no place to manage templates beyond create-via-snapshot
and delete -- no way to rename/re-describe a saved template, or to set
custom AI image style guidance without recreating it from scratch.

## Image style prompt

Added `VisualGenerationProjectConfig.image_style_prompt: str = ""`
(`backend/app/modules/beat/schemas.py`) -- free-text style guidance
appended (not replacing) the existing tone/style-derived suffix in
`imagegen_generate.py`'s `_image_prompt()`, so the vertical/no-text/
consistency instructions still always apply. Confirmed with the user
beforehand that this is free: AI image generation is a flat per-image
fee, not prompt-length-metered.

## Template editing

`save_custom_template` already upserted by id -- the only missing piece
was a router endpoint. Added `PUT /templates/{template_id}`
(`backend/app/modules/beat/router.py`), rejecting built-in ids the same
way `DELETE` already does, bumping `version` on each edit.

Frontend: new `EditTemplateModal` (Name/Description/Image style prompt)
wired into Settings' existing "Video Factory Templates" list via a new
Edit button next to Delete. Also added the same Image style prompt field
to `VideoFactoryPage`'s existing "Save as Template" modal, so it can be
set at creation time too.

## Verification

Real (non-mocked) backend tests: `update_template` round-trip, version
bump, blank-name/builtin/not-found rejections
(`tests/modules/beat/test_router.py`); `image_style_prompt` folded into
every generated beat's prompt (`tests/api/test_imagegen_stage.py`). Full
backend suite (1060 tests) and `npx tsc -b --noEmit` clean.

Playwright against the real running app: created a throwaway custom
template via the real API, opened Settings, clicked its new Edit button,
confirmed the modal pre-fills existing values, renamed it and set an
image style prompt, saved, confirmed the rename appeared in the list --
then deleted the throwaway template via the API to leave the user's real
templates untouched. Separately confirmed the same field renders in
Video Factory's "Save as Template" modal. Zero console errors in both.
