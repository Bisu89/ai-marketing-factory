import { apiDelete, apiGet, apiPost } from "./client";
import type { CaptionJob } from "../types/caption";

export function generateCaptions(videoId: number): Promise<CaptionJob> {
  return apiPost("/caption-jobs", { video_id: videoId });
}

export function listCaptionJobs(videoId?: number): Promise<CaptionJob[]> {
  const query = videoId != null ? `?video_id=${videoId}` : "";
  return apiGet(`/caption-jobs${query}`);
}

export function selectCaptionVersion(jobId: number, versionId: number): Promise<CaptionJob> {
  return apiPost(`/caption-jobs/${jobId}/versions/${versionId}/select`);
}

export function deleteCaptionJob(jobId: number): Promise<void> {
  return apiDelete(`/caption-jobs/${jobId}`);
}
