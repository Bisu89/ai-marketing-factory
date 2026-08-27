// Mirrors app/api/v1/endpoints/produced_videos.py -- the read-only browse
// of every finished Factory / Video Composer render.

export interface ProducedVideoFacet {
  id: number;
  name: string;
  count: number;
}

export interface ProducedVideo {
  render_job_id: number;
  job_status: string; // COMPLETED | FAILED | RUNNING | QUEUED | CANCELLED
  title: string;
  description: string | null;
  hashtags: string[];
  project_id: number | null;
  project_name: string | null;
  batch_id: number | null;
  batch_name: string | null;
  series_id: number | null;
  series_name: string | null;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  output_size_mb: number | null;
  render_time_seconds: number | null;
  output_path: string | null;
  output_media_url: string | null;
  thumbnail_url: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ProducedVideoList {
  total: number;
  items: ProducedVideo[];
  batches: ProducedVideoFacet[];
  series: ProducedVideoFacet[];
}

export interface ProducedVideoQuery {
  status?: "COMPLETED" | "FAILED" | "ALL";
  batch_id?: number;
  series_id?: number;
  q?: string;
  limit?: number;
  offset?: number;
}
