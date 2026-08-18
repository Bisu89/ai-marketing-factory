export type VideoComposeStatus =
  | "queued"
  | "rendering_beats"
  | "merging"
  | "narrating"
  | "subtitling"
  | "mixing_audio"
  | "finalizing"
  // Task 26 -- see docs/features/52-final-composer.md. The Final
  // Composer's own single one-pass phase (concat + captions + watermark +
  // audio mux + encode at once) -- only entered for a Factory-driven
  // render; every other job still goes through the phases above.
  | "composing_final"
  | "validating"
  | "completed"
  | "failed"
  | "cancelled";

// Task 11 -- see docs/features/38-render-job-hardening.md. Every
// VideoComposeStatus above collapses to exactly one of these 5.
export type CoarseJobStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export type RenderPhase =
  | "RENDER_BEATS"
  | "COMPOSE_VIDEO"
  | "BUILD_AUDIO"
  | "BURN_CAPTIONS"
  | "FINAL_COMPOSITION"
  | "VALIDATE_OUTPUT";

export interface VideoComposeJob {
  id: number;
  title: string;
  voice: string;
  music_volume: number;
  narration_volume: number;
  music_ducking_ratio: number;
  fade_in_sec: number;
  fade_out_sec: number;
  caption_preset: string;
  transition_duration: number;
  burn_subtitles: boolean;
  requested_output_dir: string | null;
  // Task 26 -- see docs/features/52-final-composer.md. True only for a
  // Factory-driven "Final Composer" job; always false for a plain
  // upload-based Video Composer job.
  watermark_enabled: boolean;
  status: VideoComposeStatus;
  clip_count: number;
  output_path: string | null;
  output_media_url: string | null;
  // From render_metadata.json, surfaced via job_to_out (see
  // docs/features/35-multi-beat-composition.md) -- null until the job
  // completes (or if that sidecar is missing/unreadable).
  render_duration_sec: number | null;
  render_width: number | null;
  render_height: number | null;
  render_fps: number | null;
  render_time_seconds: number | null;
  output_size_mb: number | null;
  // From .render/job_<id>/report.json, surfaced via job_to_out (Task 10 --
  // see docs/features/37-e2e-pipeline-hardening.md). Null until the job
  // completes/fails, or for a job rendered before this report existed.
  external_api_calls: number | null;
  external_api_cost_estimate: number | null;
  error_code: string | null;
  failed_phase: string | null;
  timing: Record<string, number | null> | null;
  // Derived, API-facing view of `status` above (Task 11 -- see
  // docs/features/38-render-job-hardening.md's COARSE_STATUS/RENDER_PHASE).
  job_status: CoarseJobStatus;
  phase: RenderPhase | null;
  // Live progress during RENDER_BEATS only -- both null otherwise, and
  // only ever real, known counts (never a guessed percentage).
  progress_current: number | null;
  progress_total: number | null;
  previous_job_id: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
