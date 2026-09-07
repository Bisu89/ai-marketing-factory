// Mirrors backend/app/modules/story/schemas.py + the story pipeline
// composition root (app/api/v1/endpoints/story_pipeline.py). See
// docs/features/{131,132,133}-storytelling-studio-*.md.

export const STORY_MODES = ["STORY", "HISTORY", "EDUCATION"] as const;
export type StoryMode = (typeof STORY_MODES)[number];

export const PRODUCTION_PROFILES = ["ECONOMY", "BALANCED", "PREMIUM"] as const;
export type ProductionProfile = (typeof PRODUCTION_PROFILES)[number];

export const VISUAL_MODES = ["STILL", "STILL_WITH_MOTION", "AI_VIDEO"] as const;
export type VisualMode = (typeof VISUAL_MODES)[number];
export type VisualModeSource = "AUTO" | "USER";

export interface Story {
  id: number;
  episode_id: number | null;
  mode: StoryMode;
  title: string;
  logline: string | null;
  genre: string | null;
  status: string;
  story_bible_json: Record<string, unknown>;
  style_bible_json: Record<string, unknown>;
  project_config_json: Record<string, unknown>;
  budget_usd: number | null;
  production_profile: ProductionProfile;
  reference_notes: string | null;
  content_idea_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateStoryRequest {
  title: string;
  mode: StoryMode;
  logline?: string | null;
  genre?: string | null;
  budget_usd?: number | null;
  production_profile?: ProductionProfile;
  reference_notes?: string | null;
}

export interface StoryChapter {
  id: number;
  story_id: number;
  order: number;
  title: string | null;
  summary: string | null;
  goal: string | null;
  retention_notes: string | null;
  compiled_project_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface StoryCharacter {
  id: number;
  story_id: number;
  name: string;
  role: string | null;
  age: string | null;
  gender: string | null;
  appearance: string | null;
  wardrobe: string | null;
  personality: string | null;
  canonical_prompt_block: string | null;
  negative_constraints: string | null;
  [key: string]: unknown;
}

export interface StoryScene {
  id: number;
  chapter_id: number;
  order: number;
  scene_type: string | null;
  narration: string | null;
  dialogue_json: { character_id: number; line: string }[];
  character_ids_json: number[];
  location_id: number | null;
  image_prompt: string | null;
  video_prompt: string | null;
  visual_mode: VisualMode;
  visual_mode_source: VisualModeSource;
  motion_preset: string | null;
  camera: string | null;
  lighting: string | null;
  emotion: string | null;
  time_of_day: string | null;
  continuity_notes: string | null;
  duration_hint: number;
  importance_score: number | null;
  emotion_score: number | null;
  movement_score: number | null;
  complexity_score: number | null;
  composite_score: number | null;
  est_cost_usd: number | null;
  image_asset_id: number | null;
  video_asset_id: number | null;
  reuse_asset_from_scene_id: number | null;
  approved: boolean;
  created_at: string;
  updated_at: string;
}

// -- StoryRun ----------------------------------------------------------

export const STORY_RUN_STAGES = [
  "STORY_DEVELOPMENT",
  "STORY_BIBLE",
  "CHARACTER_BIBLE",
  "CHAPTER_OUTLINE",
  "SCENE_BREAKDOWN",
  "SCENE_CLASSIFICATION",
] as const;
export type StoryRunStage = (typeof STORY_RUN_STAGES)[number];

// PRODUCE-scope stages (feature 135) -- a produce run compiles then hands
// each project to the Factory.
export const STORY_PRODUCE_STAGES = ["COMPILING", "PRODUCING"] as const;
export type StoryProduceStage = (typeof STORY_PRODUCE_STAGES)[number];

export type StoryRunStatus =
  | StoryRunStage
  | StoryProduceStage
  | "DRAFT"
  | "NEEDS_REVIEW"
  | "READY"
  | "FAILED"
  | "CANCELLED"
  | "COMPLETED";

const ACTIVE_STAGES = new Set<string>([...STORY_RUN_STAGES, ...STORY_PRODUCE_STAGES]);
export function isActiveStoryRun(status: string): boolean {
  return ACTIVE_STAGES.has(status) || status === "DRAFT";
}

export interface StoryRun {
  id: number;
  story_id: number;
  scope: string;
  status: StoryRunStatus;
  failed_stage: string | null;
  error_code: string | null;
  error_message: string | null;
  attempt: number;
  target_language: string | null;
  stage_metrics_json: Record<string, number> | null;
  est_cost_json: StoryCost | null;
  actual_cost_usd: number | null;
  compiled_project_ids_json: number[];
  requires_human_review: boolean;
  review_reason_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface StoryCheckpoint {
  id: number;
  story_run_id: number;
  stage: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED";
  attempt: number;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  checkpoint_metadata_json: Record<string, unknown> | null;
}

// -- Scene Director + cost -------------------------------------------

export type CostVerdict = "OK" | "WARN" | "BLOCK" | "UNKNOWN";

export interface StoryCost {
  story_id: number;
  verdict: CostVerdict;
  effective_cap_usd: number | null;
  cap_source: "cost_guard" | "story_budget" | "none";
  total_usd: number | null;
  estimate: {
    llm_usd: number;
    image_usd: number;
    video_usd: number | null;
    tts_usd: number;
    package_usd: number;
    master_usd: number;
    per_extra_language_usd: number;
    total_usd: number | null;
    all_prices_confirmed: boolean;
    breakdown: Record<string, unknown>;
    notes: string[];
  };
  scene_counts: Record<string, number | boolean>;
  notes: string[];
}

export interface CompiledProjectView {
  project_id: number;
  chapter_id: number | null;
  label: string;
  is_test?: boolean;
  factory_run: {
    id: number;
    status: string;
    failed_stage: string | null;
    error_message: string | null;
    render_job_id: number | null;
  } | null;
}

export interface SceneClassifyResponse {
  story_id: number;
  scenes_total: number;
  scenes_updated: number;
  scenes_frozen: number;
  ai_video_count: number;
  still_with_motion_count: number;
  still_count: number;
  reuse_count: number;
  demoted_scene_ids: string[];
}
