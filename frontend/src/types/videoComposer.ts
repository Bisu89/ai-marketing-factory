export type VideoComposeStatus = "queued" | "merging" | "finalizing" | "completed" | "failed";

export interface VideoComposeJob {
  id: number;
  title: string;
  music_volume: number;
  transition_duration: number;
  requested_output_dir: string | null;
  status: VideoComposeStatus;
  clip_count: number;
  output_path: string | null;
  output_media_url: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
