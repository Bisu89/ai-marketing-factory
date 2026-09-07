import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "./client";
import type {
  CompiledProjectView,
  CreateStoryRequest,
  SceneClassifyResponse,
  Story,
  StoryChapter,
  StoryCharacter,
  StoryCheckpoint,
  StoryCost,
  StoryRun,
  StoryScene,
} from "../types/story";

// Mirrors app.modules.story.router (pure CRUD) + the composition root
// app/api/v1/endpoints/story_pipeline.py (classify / cost / run).

export function listStories(params?: { mode?: string; status?: string }): Promise<Story[]> {
  const q = new URLSearchParams();
  if (params?.mode) q.set("mode", params.mode);
  if (params?.status) q.set("status", params.status);
  const suffix = q.toString() ? `?${q}` : "";
  return apiGet(`/stories${suffix}`);
}

export function createStory(input: CreateStoryRequest): Promise<Story> {
  return apiPost("/stories", input);
}

export function getStory(storyId: number): Promise<Story> {
  return apiGet(`/stories/${storyId}`);
}

export function patchStory(storyId: number, patch: Partial<Story>): Promise<Story> {
  return apiPatch(`/stories/${storyId}`, patch);
}

export function deleteStory(storyId: number): Promise<void> {
  return apiDelete(`/stories/${storyId}`);
}

export function listChapters(storyId: number): Promise<StoryChapter[]> {
  return apiGet(`/stories/${storyId}/chapters`);
}

export function listCharacters(storyId: number): Promise<StoryCharacter[]> {
  return apiGet(`/stories/${storyId}/characters`);
}

export function listScenes(chapterId: number): Promise<StoryScene[]> {
  return apiGet(`/story-chapters/${chapterId}/scenes`);
}

// PUT /story-scenes/{id} replaces the whole scene (StorySceneIn, extra
// forbidden) -- so callers rebuild the full input from a loaded scene.
const SCENE_INPUT_KEYS = [
  "order", "scene_type", "narration", "dialogue_json", "character_ids_json", "location_id",
  "image_prompt", "video_prompt", "visual_mode", "visual_mode_source", "motion_preset",
  "camera", "lighting", "emotion", "time_of_day", "continuity_notes", "duration_hint",
] as const;

export function updateScene(scene: StoryScene, overrides: Partial<StoryScene>): Promise<StoryScene> {
  const merged = { ...scene, ...overrides } as Record<string, unknown>;
  const body: Record<string, unknown> = {};
  for (const key of SCENE_INPUT_KEYS) body[key] = merged[key];
  return apiPut(`/story-scenes/${scene.id}`, body);
}

// -- pipeline (composition root) ------------------------------------

export function getSceneCost(storyId: number): Promise<StoryCost> {
  return apiGet(`/stories/${storyId}/cost-estimate`);
}

export function classifyScenes(storyId: number): Promise<SceneClassifyResponse> {
  return apiPost(`/stories/${storyId}/classify-scenes`);
}

export function listStoryRuns(storyId: number): Promise<StoryRun[]> {
  return apiGet(`/stories/${storyId}/runs`);
}

export function getStoryRun(runId: number): Promise<StoryRun> {
  return apiGet(`/story-runs/${runId}`);
}

export function getStoryRunCheckpoints(runId: number): Promise<StoryCheckpoint[]> {
  return apiGet(`/story-runs/${runId}/checkpoints`);
}

export function startStoryRun(storyId: number): Promise<StoryRun> {
  return apiPost(`/stories/${storyId}/runs`);
}

export function retryStoryRun(runId: number): Promise<StoryRun> {
  return apiPost(`/story-runs/${runId}/retry`);
}

export function cancelStoryRun(runId: number): Promise<StoryRun> {
  return apiPost(`/story-runs/${runId}/cancel`);
}

// -- import a story written elsewhere (skip the AI pipeline) --------

export interface StoryImportResult {
  story_id: number;
  characters: number;
  locations: number;
  chapters: number;
  scenes: number;
  unresolved_character_names: string[];
}

export function importStoryPackage(
  storyId: number,
  pkg: unknown,
  replace = false,
): Promise<StoryImportResult> {
  return apiPost(`/stories/${storyId}/import${replace ? "?replace=true" : ""}`, pkg);
}

// -- compile / produce (Phase 5) -----------------------------------

export function produceStory(storyId: number): Promise<StoryRun> {
  return apiPost(`/stories/${storyId}/produce`);
}

export function getCompiledProjects(storyId: number): Promise<{ story_id: number; projects: CompiledProjectView[] }> {
  return apiGet(`/stories/${storyId}/compiled`);
}
