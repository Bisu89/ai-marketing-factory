import { apiGet, apiPost } from "./client";
import type { ProducedVideoList, ProducedVideoQuery } from "../types/producedVideo";

// Mirrors app/api/v1/endpoints/produced_videos.py.

export function listProducedVideos(query: ProducedVideoQuery = {}): Promise<ProducedVideoList> {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.q) params.set("q", query.q);
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  const qs = params.toString();
  return apiGet(`/produced-videos${qs ? `?${qs}` : ""}`);
}

export function openDocumentaryVideoFolder(jobId: number): Promise<void> {
  return apiPost(`/produced-videos/documentary/${jobId}/open-folder`);
}

export function openProducedVideoFolder(renderJobId: number): Promise<void> {
  return apiPost(`/produced-videos/${renderJobId}/open-folder`);
}
