# 128. Settings page: cleanup + default-voice card

Reworked the Settings page after a user request to tidy it up.

**What changed**
- **Removed two dead controls**: "Số lượt tải song song tối đa" and "Chất
  lượng mặc định" only ever held local component state -- no save call, no
  backend endpoint (download quality isn't a setting anywhere). Gone.
  `max_concurrent_downloads` still exists as a backend field (used by the
  download engine); it just no longer has a no-op UI.
- **Regrouped the cards** with section headers, in producer order: Lưu trữ
  & dọn dẹp (folder + render-cache retention, previously two separate
  places) → AI Provider → Giọng đọc mặc định → TikTok → YouTube → RSS →
  Templates.
- **New "Giọng đọc mặc định (cho Template mới)" card** + backend:
  `default_voice_provider` / `default_voice_id` / `default_voice_speed` /
  `default_sentence_pause_sec` in `Settings`, `PUT /settings/default-voice`
  (validates against `VOICE_PROVIDERS` / speed / `MAX_SENTENCE_PAUSE_SEC`),
  echoed in `GET /settings`. `CreateTemplateModal` seeds its voice fields
  from these when starting from "Blank" (a copy-of-template still uses that
  template's own voice). Never touches an existing template or project.
- **`sentence_pause_sec` is now editable in the UI** for the first time
  (Create + Edit Template modals) -- it was config-only, set in Python for
  built-ins. Added to the frontend `VoiceProjectConfig` type + the
  `SYSTEM_DEFAULT_PROJECT_CONFIG` literal + `VideoFactoryPage`'s
  `buildProjectConfigForSave` (preserved as-loaded, no Step 4 control).

**Landed in**: `465e896` — feat: Settings page cleanup + default-voice card (128)

**Key files**: `backend/app/core/config.py`,
`backend/app/api/v1/endpoints/settings.py`,
`frontend/src/pages/SettingsPage.tsx`,
`frontend/src/components/{Create,Edit}TemplateModal.tsx`,
`frontend/src/types/{settings,videoFactory}.ts`,
`frontend/src/api/settings.ts`, `frontend/src/pages/VideoFactoryPage.tsx`.

**Note**: the default is a *starting point for new templates only*, chosen
over a global render-time voice override (which would surprise multi-niche
users whose templates deliberately differ). The edge_tts single-call
fallback that made `sentence_pause_sec` ineffective in one podcast voice
test is a separate pipeline issue, not addressed here.
