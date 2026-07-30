import { apiGet, apiPost } from "./client";
import type { CreateSceneJobInput, SceneCutJob } from "../types/sceneCutter";

export function createSceneJob(input: CreateSceneJobInput): Promise<SceneCutJob> {
  return apiPost("/scene-jobs", input);
}

export function listSceneJobs(): Promise<SceneCutJob[]> {
  return apiGet("/scene-jobs");
}

export function getSceneJob(jobId: number): Promise<SceneCutJob> {
  return apiGet(`/scene-jobs/${jobId}`);
}
