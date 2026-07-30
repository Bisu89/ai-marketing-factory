export type DownloadStatus = "queued" | "downloading" | "paused" | "completed" | "failed" | "cancelled";

export interface DownloadVideo {
  title: string;
  platform: string;
  thumbnail_url: string | null;
  video_path: string | null;
}

export interface DownloadTask {
  id: number;
  status: DownloadStatus;
  progress_pct: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  video: DownloadVideo;
}
