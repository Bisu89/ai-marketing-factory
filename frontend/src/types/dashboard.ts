// Mirrors backend/app/api/v1/endpoints/dashboard.py's DashboardOut exactly
// -- see docs/features/43-production-dashboard.md.

export interface DashboardSummary {
  ready: number;
  needs_review: number;
  blocked: number;
  rendering: number;
  completed_today: number;
}

export interface DashboardBatchProgress {
  batch_id: number;
  name: string;
  total: number;
  completed: number;
  // Only the real, non-zero BatchItemStatus values present in this batch.
  status_counts: Record<string, number>;
}

export interface DashboardCurrentRender {
  render_job_id: number;
  project_id: number | null;
  batch_id: number | null;
  project_name: string;
  phase: string | null;
  progress_current: number | null;
  progress_total: number | null;
  elapsed_seconds: number;
}

export type AttentionPriority = "BLOCKED" | "FAILED" | "NEEDS_REVIEW";

export interface DashboardAttentionItem {
  batch_id: number;
  item_id: number;
  project_id: number | null;
  project_name: string;
  priority: AttentionPriority;
  reason: string;
}

export interface DashboardVideo {
  render_job_id: number;
  project_id: number | null;
  batch_id: number | null;
  title: string;
  status: "COMPLETED" | "FAILED";
  duration_sec: number | null;
  render_time_seconds: number | null;
  output_media_url: string | null;
  error_message: string | null;
}

export interface DashboardQueueEntry {
  render_job_id: number;
  project_id: number | null;
  title: string;
  job_status: "RUNNING" | "QUEUED";
}

export interface DashboardPipeline {
  total_items: number;
  status_counts: Record<string, number>;
}

export interface DashboardCost {
  videos_rendered_today: number;
  external_video_api_calls: number;
  external_video_api_cost: number;
}

export interface DashboardOut {
  has_any_data: boolean;
  summary: DashboardSummary;
  current_batch: DashboardBatchProgress | null;
  current_render: DashboardCurrentRender | null;
  attention: DashboardAttentionItem[];
  attention_total: number;
  recent_videos: DashboardVideo[];
  recent_failures: DashboardVideo[];
  queue: DashboardQueueEntry[];
  pipeline: DashboardPipeline;
  cost: DashboardCost;
}
