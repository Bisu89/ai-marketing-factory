import { apiGet, apiPost } from "./client";
import type { ProducedVideoList, ProducedVideoQuery } from "../types/producedVideo";

// Mirrors app/api/v1/endpoints/produced_videos.py.

export function listProducedVideos(query: ProducedVideoQuery = {}): Promise<ProducedVideoList> {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.batch_id != null) params.set("batch_id", String(query.batch_id));
  if (query.series_id != null) params.set("series_id", String(query.series_id));
  if (query.q) params.set("q", query.q);
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  const qs = params.toString();
  return apiGet(`/produced-videos${qs ? `?${qs}` : ""}`);
}

export function openProducedVideoFolder(renderJobId: number): Promise<void> {
  return apiPost(`/produced-videos/${renderJobId}/open-folder`);
}
