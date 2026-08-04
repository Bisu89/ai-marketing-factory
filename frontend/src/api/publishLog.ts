import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  DimensionBreakdown,
  PerformanceOverview,
  PublishLog,
  PublishLogCreateInput,
  PublishLogUpdateInput,
  UnlinkedPost,
} from "../types/publishLog";

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

export function linkPublishLogToPost(logId: number, postId: string, pageId: string): Promise<PublishLog> {
  return apiPost(`/publish-logs/${logId}/link-post`, { post_id: postId, page_id: pageId });
}

export function unlinkPublishLog(logId: number): Promise<PublishLog> {
  return apiPost(`/publish-logs/${logId}/unlink`);
}

export function listUnlinkedPosts(): Promise<UnlinkedPost[]> {
  return apiGet("/insights/unlinked-posts");
}

export function getPerformanceOverview(): Promise<PerformanceOverview> {
  return apiGet("/performance/overview");
}

export function getWinners(limit = 10): Promise<PublishLog[]> {
  return apiGet(`/performance/winners?limit=${limit}`);
}

export function getLosers(limit = 10): Promise<PublishLog[]> {
  return apiGet(`/performance/losers?limit=${limit}`);
}

export type { DimensionBreakdown };
