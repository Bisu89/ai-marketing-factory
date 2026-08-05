import { apiDelete, apiGet, apiPost } from "./client";
import type { HookJob } from "../types/hook";

export function generateHooks(videoId: number): Promise<HookJob> {
  return apiPost("/hook-jobs", { video_id: videoId });
}

export function listHookJobs(videoId?: number): Promise<HookJob[]> {
  const query = videoId != null ? `?video_id=${videoId}` : "";
  return apiGet(`/hook-jobs${query}`);
}

export function toggleHookFavorite(jobId: number, hookId: number): Promise<HookJob> {
  return apiPost(`/hook-jobs/${jobId}/hooks/${hookId}/favorite`);
}

export function deleteHookJob(jobId: number): Promise<void> {
  return apiDelete(`/hook-jobs/${jobId}`);
}
