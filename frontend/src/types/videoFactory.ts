// Mirrors backend/app/modules/composition/schemas.py (Scene, CompositionPlan
// and their nested shapes) -- this is the literal request body shape for
// POST /video-compose-jobs/from-composition
// (backend/app/api/v1/endpoints/composition_render.py), so field names and
// value bounds must match the Pydantic contract exactly or the backend
// rejects the request with a 422.
//
// Beat generation itself is a real backend call now (POST /beats/generate,
// see api/beat.ts and docs/features/30-generate-beats.md) -- app.modules.beat
// is still a contract-only module with no router of its own, but
// app/api/v1/endpoints/beat_generate.py adapts it with the existing AI
// infrastructure. There is still no backend endpoint listing motion/caption
// presets (both are small, stable, already-documented sets), so those stay
// client-side per this feature's original "keep it simple" convention.

export type MotionPresetName =
  | "static"
  | "slow_push_in"
  | "slow_pull_out"
  | "pan_left"
  | "pan_right"
  | "pan_up"
  | "pan_down"
  | "zoom_and_pan"
  | "subtle_rotate";

export const MOTION_PRESETS: MotionPresetName[] = [
  "static",
  "slow_push_in",
  "slow_pull_out",
  "pan_left",
  "pan_right",
  "pan_up",
  "pan_down",
  "zoom_and_pan",
  "subtle_rotate",
];

export const MOTION_PRESET_LABELS: Record<MotionPresetName, string> = {
  static: "Static (no motion)",
  slow_push_in: "Slow push in",
  slow_pull_out: "Slow pull out",
  pan_left: "Pan left",
  pan_right: "Pan right",
  pan_up: "Pan up",
  pan_down: "Pan down",
  zoom_and_pan: "Zoom + pan",
  subtle_rotate: "Subtle rotate",
};

export type CaptionPreset = "emotional" | "cinematic" | "word_highlight" | "big_statement" | "quote" | "top";

export const CAPTION_PRESETS: CaptionPreset[] = [
  "emotional", "cinematic", "word_highlight", "big_statement", "quote", "top",
];

export const CAPTION_PRESET_LABELS: Record<CaptionPreset, string> = {
  emotional: "Emotional (highlight box)",
  cinematic: "Cinematic (clean subtitle)",
  word_highlight: "Word highlight",
  big_statement: "Big statement",
  quote: "Quote",
  top: "Top (small, below the top edge)",
};

export type Easing = "linear" | "ease_in" | "ease_out" | "ease_in_out";
export type TransitionType = "cut" | "crossfade" | "slide_left" | "slide_right" | "fade_to_black";

// Mirrors backend/app/modules/beat/schemas.py's BeatType exactly (see
// docs/features/29-beat-domain-contract-v2.md) -- values are the literal
// strings the backend serializes/accepts.
export type BeatType = "HOOK" | "SETUP" | "BUILD" | "REVEAL" | "REACTION" | "ENDING" | "BODY";

export const BEAT_TYPES: BeatType[] = ["HOOK", "SETUP", "BUILD", "REVEAL", "REACTION", "ENDING", "BODY"];

// Mirrors backend/app/modules/beat/schemas.py's BeatMotionPreset exactly
// (see docs/features/33-motion-presets-beat-motion-assignment.md) -- the
// presets a Beat itself can declare, persisted via beats.json. This is
// deliberately NOT the same set as MotionPresetName/MOTION_PRESET_DEFAULTS
// below (9 lowercase presets used to build a render-time Scene.motion) --
// see that section's comment for how the two relate. Every value here is a
// strict subset of MOTION_PRESET_DEFAULTS' keys (same spelling, just upper
// vs lower case), so resolving one into the other is a plain
// `.toLowerCase()`, not a lookup table. PAN_UP/PAN_DOWN added in Task 23
// (see docs/features/49-local-motion-engine.md section 6/58).
export type BeatMotionPreset =
  | "STATIC"
  | "SLOW_PUSH_IN"
  | "SLOW_PULL_OUT"
  | "PAN_LEFT"
  | "PAN_RIGHT"
  | "PAN_UP"
  | "PAN_DOWN"
  | "ZOOM_AND_PAN";

export const BEAT_MOTION_PRESETS: BeatMotionPreset[] = [
  "STATIC",
  "SLOW_PUSH_IN",
  "SLOW_PULL_OUT",
  "PAN_LEFT",
  "PAN_RIGHT",
  "PAN_UP",
  "PAN_DOWN",
  "ZOOM_AND_PAN",
];

export const BEAT_MOTION_PRESET_LABELS: Record<BeatMotionPreset, string> = {
  STATIC: "Static",
  SLOW_PUSH_IN: "Slow Push In",
  SLOW_PULL_OUT: "Slow Pull Out",
  PAN_LEFT: "Pan Left",
  PAN_RIGHT: "Pan Right",
  PAN_UP: "Pan Up",
  PAN_DOWN: "Pan Down",
  ZOOM_AND_PAN: "Zoom + Pan",
};

export const BEAT_MOTION_PRESET_DESCRIPTIONS: Record<BeatMotionPreset, string> = {
  STATIC: "No camera movement.",
  SLOW_PUSH_IN: "Gradually zoom toward the image.",
  SLOW_PULL_OUT: "Gradually zoom away.",
  PAN_LEFT: "Camera moves from right to left.",
  PAN_RIGHT: "Camera moves from left to right.",
  PAN_UP: "Camera moves from bottom to top.",
  PAN_DOWN: "Camera moves from top to bottom.",
  ZOOM_AND_PAN: "Slow zoom combined with subtle camera movement.",
};

// -- Scene contract (mirrors app.modules.composition.schemas) ----------------

export interface ScaleRange {
  start: number;
  end: number;
}

export interface PositionRange {
  x_start: number;
  y_start: number;
  x_end: number;
  y_end: number;
}

export interface RotationRange {
  start: number;
  end: number;
}

export interface SceneMotion {
  preset_name: string | null;
  scale: ScaleRange;
  position: PositionRange;
  rotation: RotationRange;
  easing: Easing;
}

export interface SceneCaption {
  text: string | null;
  preset: CaptionPreset | null;
}

export interface SceneAudio {
  sfx: string | null;
  sfx_volume: number;
  narration_asset_id: number | null;
}

export interface SceneTransition {
  type: TransitionType;
  duration: number;
}

export interface OutputFormat {
  width: number;
  height: number;
  fps: number;
}

export interface Scene {
  id: string;
  order: number;
  beat_id: string | null;
  duration: number;
  source_asset_id: number;
  motion: SceneMotion;
  caption: SceneCaption;
  audio: SceneAudio;
  transition: SceneTransition;
  output_format: OutputFormat;
}

export interface CompositionPlan {
  video_id: number | null;
  narration_script: string | null;
  voice: string;
  language: string | null;
  narration_volume: number;
  music_path: string | null;
  music_volume: number;
  music_ducking_ratio: number;
  fade_in_sec: number;
  fade_out_sec: number;
  caption_preset: CaptionPreset;
  scenes: Scene[];
}

// -- Motion preset numeric defaults --------------------------------------------
//
// Mirrors backend/app/modules/motion/service.py's _PRESET_DEFAULTS exactly
// (scale/position/rotation per preset) -- duplicated, not fetched, for the
// same "duplicate the pattern, don't import across a boundary that can't be
// crossed" reason every other Python<->TS or module<->module boundary in
// this codebase uses (see e.g. app/modules/composition/schemas.py's own
// module docstring). The renderer itself never branches on the preset name
// (see docs/features/23-local-motion-renderer.md) -- these numeric values
// are what actually produce the look each preset name promises.
export const MOTION_PRESET_DEFAULTS: Record<
  MotionPresetName,
  { scale: ScaleRange; position: PositionRange; rotation: RotationRange }
> = {
  static: {
    scale: { start: 1.0, end: 1.0 },
    position: { x_start: 0.5, y_start: 0.5, x_end: 0.5, y_end: 0.5 },
    rotation: { start: 0.0, end: 0.0 },
  },
  slow_push_in: {
    scale: { start: 1.0, end: 1.08 },
    position: { x_start: 0.5, y_start: 0.5, x_end: 0.52, y_end: 0.48 },
    rotation: { start: 0.0, end: 0.0 },
  },
  slow_pull_out: {
    scale: { start: 1.08, end: 1.0 },
    position: { x_start: 0.52, y_start: 0.48, x_end: 0.5, y_end: 0.5 },
    rotation: { start: 0.0, end: 0.0 },
  },
  pan_left: {
    scale: { start: 1.15, end: 1.15 },
    position: { x_start: 0.6, y_start: 0.5, x_end: 0.4, y_end: 0.5 },
    rotation: { start: 0.0, end: 0.0 },
  },
  pan_right: {
    scale: { start: 1.15, end: 1.15 },
    position: { x_start: 0.4, y_start: 0.5, x_end: 0.6, y_end: 0.5 },
    rotation: { start: 0.0, end: 0.0 },
  },
  pan_up: {
    scale: { start: 1.15, end: 1.15 },
    position: { x_start: 0.5, y_start: 0.6, x_end: 0.5, y_end: 0.4 },
    rotation: { start: 0.0, end: 0.0 },
  },
  pan_down: {
    scale: { start: 1.15, end: 1.15 },
    position: { x_start: 0.5, y_start: 0.4, x_end: 0.5, y_end: 0.6 },
    rotation: { start: 0.0, end: 0.0 },
  },
  zoom_and_pan: {
    scale: { start: 1.0, end: 1.15 },
    position: { x_start: 0.5, y_start: 0.5, x_end: 0.6, y_end: 0.4 },
    rotation: { start: 0.0, end: 0.0 },
  },
  subtle_rotate: {
    scale: { start: 1.05, end: 1.05 },
    position: { x_start: 0.5, y_start: 0.5, x_end: 0.5, y_end: 0.5 },
    rotation: { start: -3.0, end: 3.0 },
  },
};

// -- AI beat generation (mirrors backend/app/modules/beat/schemas.py's
// Beat/BeatPlan, as returned by POST /beats/generate) -------------------

export interface GeneratedBeat {
  id: string;
  order: number;
  type: BeatType;
  narration: string | null;
  duration: number;
  visual_hint: string | null;
  asset_id: number | null;
  // null = "not explicitly set -- inherit ProjectConfig.motion.default_preset"
  // (Task 12, see docs/features/39-project-templates.md and
  // effectiveMotionPreset() below); AI-generated beats always arrive this
  // way (beat generation never assigns a motion preset).
  motion_preset: BeatMotionPreset | null;
  // A local, pre-recorded narration audio Asset (type="audio") for this
  // beat -- see docs/features/36-audio-pipeline.md. null means "no local
  // narration for this beat" (silence in local mode, or -- if no beat in
  // the plan has one set -- this beat's `narration` text spoken via the
  // existing TTS path instead).
  narration_asset_id: number | null;
}

// -- Project configuration + templates (Task 12) -----------------------------
// Mirrors backend/app/modules/beat/schemas.py's ProjectConfig/Template
// exactly -- see docs/features/39-project-templates.md.

export interface RenderProjectConfig {
  profile: string;
}

// Task 23 -- see docs/features/49-local-motion-engine.md sections 26/29/58.
export type MotionIntensity = "SUBTLE" | "MEDIUM" | "STRONG";
export type ShortVideoPolicy = "LOOP" | "FREEZE" | "REJECT";

export interface MotionProjectConfig {
  default_preset: BeatMotionPreset;
  auto_rotate: boolean;
  intensity: MotionIntensity;
  short_video_policy: ShortVideoPolicy;
}

// Task 25 -- see docs/features/51-caption-engine.md sections 5/6/9/10.
export interface CaptionsProjectConfig {
  enabled: boolean;
  preset: CaptionPreset;
  max_words: number;
  max_chars: number;
  min_duration_sec: number;
  max_duration_sec: number;
  max_lines: number;
  reading_speed_wps: number;
}

// Task 26 -- see docs/features/52-final-composer.md sections 18-23.
export type WatermarkPosition = "top-left" | "top-right" | "bottom-left" | "bottom-right";
export const WATERMARK_POSITIONS: WatermarkPosition[] = ["top-left", "top-right", "bottom-left", "bottom-right"];
export const WATERMARK_POSITION_LABELS: Record<WatermarkPosition, string> = {
  "top-left": "Top left",
  "top-right": "Top right",
  "bottom-left": "Bottom left",
  "bottom-right": "Bottom right",
};

export interface WatermarkProjectConfig {
  enabled: boolean;
  asset_id: number | null;
  position: WatermarkPosition;
  opacity: number;
  scale: number;
  margin_x: number;
  margin_y: number;
}

// Task 24 -- see docs/features/50-audio-master.md sections 7/8/9/33.
export type BgmMode = "AUTO" | "MANUAL";
export type BgmMissingPolicy = "OFF" | "NEEDS_REVIEW";

export interface AudioProjectConfig {
  narration_enabled: boolean;
  music_enabled: boolean;
  music_volume: number;
  ducking: boolean;
  bgm_mode: BgmMode;
  bgm_asset_id: number | null;
  ducking_ratio: number;
  fade_in_sec: number;
  fade_out_sec: number;
  bgm_missing_policy: BgmMissingPolicy;
}

// Task 18 -- see docs/features/44-one-click-factory-pipeline.md.
export interface FactoryProjectConfig {
  auto_assign_high_confidence: boolean;
  require_review_for_medium_confidence: boolean;
  require_review_for_low_confidence: boolean;
  render_after_quality_pass: boolean;
}

// Task 21 -- see docs/features/47-content-brief-script-engine.md. The
// Template-driven "content profile" Idea->ContentBrief->Script generation
// reads (language/tone/style/target duration/audience/CTA).
export interface ContentProjectConfig {
  language: string;
  tone: string;
  style: string;
  target_duration: number;
  audience: string;
  cta_enabled: boolean;
}

// Task 22 -- see docs/features/48-voice-factory-local-tts.md. `provider`
// "local" is genuinely offline SAPI5 (this app's own default, no network
// call); "edge_tts" is the existing, already-in-repo free-but-networked
// engine, kept as an explicit opt-in, never the default.
export interface VoiceProjectConfig {
  provider: "local" | "edge_tts";
  voice_id: string;
  language: string;
  speed: number;
  pitch: number;
}

// Task 59 -- see docs/features/59-ai-image-generation.md. "library" (the
// default) is today's existing behavior unchanged -- ASSIGNING_ASSETS
// matches an existing local Asset. "ai_generated" is the new opt-in
// "Generate Full by AI" mode -- a fresh OpenAI image per beat instead.
export interface VisualGenerationProjectConfig {
  mode: "library" | "ai_generated";
}

export interface ProjectConfig {
  render: RenderProjectConfig;
  motion: MotionProjectConfig;
  captions: CaptionsProjectConfig;
  audio: AudioProjectConfig;
  watermark: WatermarkProjectConfig;
  factory: FactoryProjectConfig;
  content: ContentProjectConfig;
  voice: VoiceProjectConfig;
  visual_generation: VisualGenerationProjectConfig;
  template_id: string | null;
  template_version: number | null;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  version: number;
  builtin: boolean;
  config: ProjectConfig;
}

export const SYSTEM_DEFAULT_PROJECT_CONFIG: ProjectConfig = {
  render: { profile: "SOCIAL_VERTICAL" },
  motion: { default_preset: "STATIC", auto_rotate: false, intensity: "MEDIUM", short_video_policy: "FREEZE" },
  captions: {
    enabled: true, preset: "emotional", max_words: 7, max_chars: 42,
    min_duration_sec: 0.8, max_duration_sec: 3.5, max_lines: 2, reading_speed_wps: 3.3,
  },
  watermark: {
    enabled: false, asset_id: null, position: "bottom-right", opacity: 0.8, scale: 0.15, margin_x: 24, margin_y: 24,
  },
  audio: {
    narration_enabled: true, music_enabled: true, music_volume: 0.15, ducking: true,
    bgm_mode: "AUTO", bgm_asset_id: null, ducking_ratio: 8.0, fade_in_sec: 0.5, fade_out_sec: 1.0,
    bgm_missing_policy: "OFF",
  },
  factory: {
    auto_assign_high_confidence: true,
    require_review_for_medium_confidence: true,
    require_review_for_low_confidence: true,
    render_after_quality_pass: true,
  },
  content: {
    language: "en",
    tone: "warm and reflective",
    style: "storytelling",
    target_duration: 30,
    audience: "general audience",
    cta_enabled: true,
  },
  voice: {
    provider: "local",
    voice_id: "default",
    language: "en",
    speed: 1.0,
    pitch: 0,
  },
  visual_generation: { mode: "library" },
  template_id: null,
  template_version: null,
};

// Beat override > Project default > System default (Task 12 section 11) --
// mirrors backend/app/modules/beat/schemas.py's effective_motion_preset()
// exactly. Kept as this one function (not spread across UI components) so
// every place that needs "what motion does this beat actually use" agrees.
export function effectiveMotionPreset(
  beatMotionPreset: BeatMotionPreset | null,
  config: ProjectConfig,
): BeatMotionPreset {
  return beatMotionPreset ?? config.motion.default_preset;
}

// Mirrors backend/app/api/v1/endpoints/beat_preview.py's request/response
// shapes (see docs/features/34-local-motion-renderer.md).
export interface BeatPreviewRequest {
  asset_id: number;
  motion_preset: BeatMotionPreset;
  duration: number;
}

export interface BeatPreviewResult {
  preview_media_url: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  render_time_seconds: number;
}

// Task 21 -- see docs/features/47-content-brief-script-engine.md. Not
// editable through this page in this task (no UI surfaces it yet) --
// carried through save round-trips purely so it's never silently dropped
// (see GeneratedBeatPlan's own fields below).
export interface ContentBrief {
  topic: string;
  audience: string;
  angle: string;
  emotion: string;
  hook_strategy: string;
  tone: string;
  pacing: string;
  core_message: string;
  cta: string;
}

export interface GeneratedBeatPlan {
  video_id: number | null;
  script_text: string | null;
  beats: GeneratedBeat[];
  total_duration: number;
  // Task 12 -- both default (via the backend's own Field default_factory)
  // when absent, so an old, pre-Task-12 saved beats.json still loads fine.
  project_name?: string | null;
  config?: ProjectConfig;
  // Task 21 -- see ContentBrief's own comment above; all optional/absent
  // for every pre-Task-21 saved plan.
  idea?: string | null;
  content_brief?: ContentBrief | null;
  script_locked?: boolean;
}

// -- Multi-project store (Task 13) ---------------------------------------
// Mirrors backend/app/modules/beat/schemas.py's ProjectOut -- a real,
// independently-addressable project (see docs/features/40-batch-video-creation.md),
// separate from the single "current" beats.json plan GeneratedBeatPlan
// represents above. Same shape plus id/slug/render_job_id, and `beats` can
// legitimately be empty (a just-created batch project has none until
// "Generate Beats" runs) -- unlike GeneratedBeatPlan there's no min-length
// expectation here.
export interface Project extends GeneratedBeatPlan {
  id: number;
  slug: string;
  render_job_id: number | null;
}

// -- Frontend-only working model for a beat, before it becomes a Scene -------

export type AssetAssignmentStatus = "unregistered" | "registering" | "registered" | "error";

export interface WorkingBeat {
  id: string;
  order: number;
  type: BeatType;
  narration: string;
  duration: number;
  visualHint: string | null;
  // The Beat-level, persisted preset (6 values) -- see BeatMotionPreset
  // above. null means "inherit the project's default" (Task 12,
  // effectiveMotionPreset()) -- resolved to a concrete value for display
  // and, via one of MOTION_PRESET_DEFAULTS' 9 lowercase entries, at the
  // point a Scene is built for rendering (buildScene() in
  // VideoFactoryPage.tsx). Never silently upgraded to a concrete value
  // just by being displayed -- only an explicit user choice sets it.
  motionPreset: BeatMotionPreset | null;
  assetPath: string;
  assetId: number | null;
  assetStatus: AssetAssignmentStatus;
  assetError: string | null;
  // Local narration audio for this beat -- same "path resolved separately
  // from id" shape as assetPath/assetId/assetStatus/assetError above.
  narrationAssetPath: string;
  narrationAssetId: number | null;
  narrationAssetStatus: AssetAssignmentStatus;
  narrationAssetError: string | null;
}
