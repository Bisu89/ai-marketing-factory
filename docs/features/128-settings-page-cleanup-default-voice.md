# 128. Settings page cleanup + editable sentence pause

Reworked the Settings page after a user request to tidy it up.

**What changed**
- **Removed two dead controls**: "Số lượt tải song song tối đa" and "Chất
  lượng mặc định" only ever held local component state -- no save call, no
  backend endpoint (download quality isn't a setting anywhere). Gone.
  `max_concurrent_downloads` still exists as a backend field (used by the
  download engine); it just no longer has a no-op UI.
- **Regrouped the cards** with section headers, in producer order: Lưu trữ
  & dọn dẹp (folder + render-cache retention, previously two separate
  cards) → AI Provider → TikTok → YouTube → RSS → Templates.
- **`sentence_pause_sec` is now editable in the UI** (Create + Edit
  Template modals) -- it was config-only, set in Python for the built-ins.
  Added to the frontend `VoiceProjectConfig` type + the
  `SYSTEM_DEFAULT_PROJECT_CONFIG` literal + `VideoFactoryPage`'s
  `buildProjectConfigForSave` (preserved as-loaded, no Step 4 control).

**Landed in**: `465e896` (+ `28c0065` crash-guard, then trimmed back to
this scope in a follow-up)

**Key files**: `frontend/src/pages/SettingsPage.tsx`,
`frontend/src/components/{Create,Edit}TemplateModal.tsx`,
`frontend/src/types/videoFactory.ts`,
`frontend/src/pages/VideoFactoryPage.tsx`.

**Dropped**: an earlier version added a Settings-level "default voice"
card + `default_voice_*` settings + `PUT /settings/default-voice` to
pre-fill a new template's voice. Removed at the user's request -- the
voice already lives per-template (Create/Edit Template modals), so a
separate global default was redundant.
