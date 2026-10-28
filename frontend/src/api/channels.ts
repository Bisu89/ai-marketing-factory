import { apiDelete, apiGet, apiPost } from "./client";

export type ChannelPlatform = "youtube" | "facebook";

export interface OwnedChannel {
  id: number;
  platform: ChannelPlatform;
  name: string;
  external_id: string;
  has_credential: boolean;
  last_synced_at: string | null;
  last_sync_status: "running" | "ok" | "error" | null;
  last_sync_message: string | null;
  created_at: string;
}

export interface ChannelMetric {
  day: string;
  followers: number | null;
  total_views: number | null;
  video_count: number | null;
}

export interface SyncRun {
  id: number;
  channel_id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "error";
  message: string | null;
}

export interface ChannelCreateInput {
  platform: ChannelPlatform;
  name: string;
  external_id: string;
  credential?: string;
}

export const listChannels = () => apiGet<OwnedChannel[]>("/channels");
export const createChannel = (input: ChannelCreateInput) => apiPost<OwnedChannel>("/channels", input);
export const deleteChannel = (id: number) => apiDelete<void>(`/channels/${id}`);
export const syncChannel = (id: number) => apiPost<SyncRun>(`/channels/${id}/sync`);
export const getChannelMetrics = (id: number) => apiGet<ChannelMetric[]>(`/channels/${id}/metrics`);
