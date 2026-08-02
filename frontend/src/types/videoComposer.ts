export type VideoComposeStatus =
  | "queued"
  | "merging"
  | "narrating"
  | "subtitling"
  | "mixing_audio"
  | "finalizing"
  | "completed"
  | "failed";

export interface VideoComposeJob {
  id: number;
  title: string;
  voice: string;
  music_volume: number;
  transition_duration: number;
  burn_subtitles: boolean;
  requested_output_dir: string | null;
  status: VideoComposeStatus;
  clip_count: number;
  output_path: string | null;
  output_media_url: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
