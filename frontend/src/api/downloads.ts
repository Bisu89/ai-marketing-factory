import { apiGet, apiPost } from "./client";
import type { Platform, VideoInfo } from "../types/video";
import type { DownloadTask } from "../types/download";

export async function enqueueDownload(platform: Platform, video: VideoInfo): Promise<void> {
  await apiPost("/downloads", {
    url: video.originalUrl,
    metadata: {
      platform,
      video_id: video.id,
      channel_name: video.author,
      title: video.title,
      original_url: video.originalUrl,
      thumbnail_url: video.thumbnailUrl,
      views: video.views,
      duration_sec: video.durationSec,
      upload_date: video.uploadDate,
    },
  });
}

export async function listDownloads(): Promise<DownloadTask[]> {
  return apiGet<DownloadTask[]>("/downloads");
}

export async function openDownloadFolder(taskId: number): Promise<{ path: string }> {
  return apiPost<{ path: string }>(`/downloads/${taskId}/open-folder`, {});
}
