export type UploadJobStatus = "pending" | "uploading" | "completed" | "failed" | "interrupted";
export type YouTubePrivacy = "private" | "unlisted" | "public";

export interface YouTubeChannel {
  id: number;
  channel_id: string;
  title: string;
  thumbnail_url: string | null;
  enabled: boolean;
  last_error: string | null;
  created_at: string | null;
  upload_count: number | null;
}

export interface YouTubeUploadJob {
  id: number;
  channel_pk: number;
  channel_title: string | null;
  project_id: number;
  status: UploadJobStatus;
  requested_privacy: YouTubePrivacy;
  title: string | null;
  youtube_video_id: string | null;
  watch_url: string | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}
