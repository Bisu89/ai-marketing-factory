import { config } from "../config/env";
import { apiGet, apiPost } from "./client";
import type { CreateSceneJobInput, ScenePreview, SceneCutJob } from "../types/sceneCutter";

export function createSceneJob(input: CreateSceneJobInput): Promise<SceneCutJob> {
  return apiPost("/scene-jobs", input);
}

// docs/features/107-scene-cutter-false-split-fix.md's Preview follow-up.
export function previewSceneJob(input: CreateSceneJobInput): Promise<ScenePreview> {
  return apiPost("/scene-jobs/preview", input);
}

export async function previewSceneJobUpload(
  file: File,
  threshold: number,
  minSceneLenSec: number,
  trimSec: number,
): Promise<ScenePreview> {
  const form = new FormData();
  form.set("file", file);
  form.set("threshold", String(threshold));
  form.set("min_scene_len_sec", String(minSceneLenSec));
  form.set("trim_sec", String(trimSec));

  const response = await fetch(`${config.apiBaseUrl}/scene-jobs/preview/upload`, { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `API request failed: ${response.status}`);
  }
  return response.json();
}

export interface UploadSceneJobInput {
  file: File;
  threshold: number;
  min_scene_len_sec: number;
  trim_sec: number;
  output_dir?: string;
}

export async function uploadSceneJob(input: UploadSceneJobInput): Promise<SceneCutJob> {
  const form = new FormData();
  form.set("file", input.file);
  form.set("threshold", String(input.threshold));
  form.set("min_scene_len_sec", String(input.min_scene_len_sec));
  form.set("trim_sec", String(input.trim_sec));
  if (input.output_dir) form.set("output_dir", input.output_dir);

  // No Content-Type header here on purpose -- the browser sets
  // multipart/form-data with the correct boundary itself when the body is
  // a FormData; setting it manually breaks the boundary.
  const response = await fetch(`${config.apiBaseUrl}/scene-jobs/upload`, { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `API request failed: ${response.status}`);
  }
  return response.json();
}

export function listSceneJobs(): Promise<SceneCutJob[]> {
  return apiGet("/scene-jobs");
}

export function getSceneJob(jobId: number): Promise<SceneCutJob> {
  return apiGet(`/scene-jobs/${jobId}`);
}

export function openSceneJobFolder(jobId: number): Promise<void> {
  return apiPost(`/scene-jobs/${jobId}/open-folder`);
}

export async function pickOutputFolder(): Promise<string | null> {
  const result = await apiPost<{ path: string | null }>("/scene-jobs/pick-folder");
  return result.path;
}
