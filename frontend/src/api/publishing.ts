import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type { YouTubeChannel, YouTubeUploadJob, YouTubePrivacy } from "../types/publishing";

export function getYouTubeAuthorizeUrl(): Promise<{ authorize_url: string }> {
  return apiGet("/publishing/youtube/oauth/authorize-url");
}

export function fetchYouTubeChannels(): Promise<YouTubeChannel[]> {
  return apiGet("/publishing/youtube/channels");
}

export function setChannelEnabled(channelPk: number, enabled: boolean): Promise<YouTubeChannel> {
  return apiPatch(`/publishing/youtube/channels/${channelPk}`, { enabled });
}

export function disconnectYouTubeChannel(channelPk: number): Promise<void> {
  return apiDelete(`/publishing/youtube/channels/${channelPk}`);
}

export function fetchYouTubeUploads(): Promise<YouTubeUploadJob[]> {
  return apiGet("/publishing/youtube/uploads");
}

export function uploadToYouTube(input: {
  project_id: number;
  channel_id: number;
  privacy: YouTubePrivacy;
}): Promise<{ upload_job_id: number; status: string }> {
  return apiPost("/publishing/youtube/upload", input);
}

export function retryYouTubeUpload(jobId: number): Promise<YouTubeUploadJob> {
  return apiPost(`/publishing/youtube/uploads/${jobId}/retry`);
}
