// Mirrors backend/app/modules/composition/schemas.py (Scene, CompositionPlan
// and their nested shapes) -- this is the literal request body shape for
// POST /video-compose-jobs/from-composition
// (backend/app/api/v1/endpoints/composition_render.py), so field names and
// value bounds must match the Pydantic contract exactly or the backend
// rejects the request with a 422.
//
// There is no backend beat-generation endpoint (app.modules.beat is a
// contract-only module with no router -- see
// docs/features/19-beat-domain-contract.md) and no backend endpoint
// listing motion/caption presets (both are small, stable, already-
// documented sets). Per this task's "keep it simple, do not overbuild"
// instruction, beat generation and preset option lists are implemented
// client-side instead of adding new backend endpoints for them.

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

export type CaptionPreset = "emotional" | "cinematic" | "word_highlight" | "big_statement" | "quote";

export const CAPTION_PRESETS: CaptionPreset[] = ["emotional", "cinematic", "word_highlight", "big_statement", "quote"];

export const CAPTION_PRESET_LABELS: Record<CaptionPreset, string> = {
  emotional: "Emotional (highlight box)",
  cinematic: "Cinematic (clean subtitle)",
  word_highlight: "Word highlight",
  big_statement: "Big statement",
  quote: "Quote",
};

export type Easing = "linear" | "ease_in" | "ease_out" | "ease_in_out";
export type TransitionType = "cut" | "crossfade" | "slide_left" | "slide_right" | "fade_to_black";
export type BeatType = "hook" | "body" | "cta" | "outro";

export const BEAT_TYPES: BeatType[] = ["hook", "body", "cta", "outro"];

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

// -- Frontend-only working model for a beat, before it becomes a Scene -------

export type AssetAssignmentStatus = "unregistered" | "registering" | "registered" | "error";

export interface WorkingBeat {
  id: string;
  order: number;
  type: BeatType;
  narration: string;
  duration: number;
  motionPreset: MotionPresetName;
  assetPath: string;
  assetId: number | null;
  assetStatus: AssetAssignmentStatus;
  assetError: string | null;
}
