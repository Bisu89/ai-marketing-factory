import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type { PublishLog, PublishLogCreateInput, PublishLogUpdateInput } from "../types/publishLog";

export function createPublishLog(input: PublishLogCreateInput): Promise<PublishLog> {
  return apiPost("/publish-logs", input);
}

export function listPublishLogs(videoId?: number): Promise<PublishLog[]> {
  const query = videoId != null ? `?video_id=${videoId}` : "";
  return apiGet(`/publish-logs${query}`);
}

export function updatePublishLog(logId: number, patch: PublishLogUpdateInput): Promise<PublishLog> {
  return apiPut(`/publish-logs/${logId}`, patch);
}

export function deletePublishLog(logId: number): Promise<void> {
  return apiDelete(`/publish-logs/${logId}`);
}
