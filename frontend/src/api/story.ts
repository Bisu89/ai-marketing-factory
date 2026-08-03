import { apiDelete, apiGet, apiPost } from "./client";
import type { StoryGenerateInput, StoryJob } from "../types/story";

export function generateStory(input: StoryGenerateInput): Promise<StoryJob> {
  return apiPost("/story-jobs", input);
}

export function listStoryJobs(videoId?: number): Promise<StoryJob[]> {
  const query = videoId != null ? `?video_id=${videoId}` : "";
  return apiGet(`/story-jobs${query}`);
}

export function getStoryJob(jobId: number): Promise<StoryJob> {
  return apiGet(`/story-jobs/${jobId}`);
}

export function selectStoryVersion(jobId: number, versionId: number): Promise<StoryJob> {
  return apiPost(`/story-jobs/${jobId}/versions/${versionId}/select`);
}

export function deleteStoryJob(jobId: number): Promise<void> {
  return apiDelete(`/story-jobs/${jobId}`);
}
