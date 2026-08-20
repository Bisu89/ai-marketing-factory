// Mirrors backend/app/modules/content_batch/schemas.py exactly -- see
// docs/features/71-batch-content-generation.md.

export type ContentBatchStatus = "DRAFT" | "PROCESSING" | "COMPLETED" | "PARTIAL_FAILURE" | "FAILED" | "CANCELLED";

export type ContentBatchItemStatus =
  | "PENDING"
  | "GENERATING"
  | "COMPLETED"
  | "SCORED"
  | "APPROVED"
  | "REJECTED"
  | "FAILED"
  | "CANCELLED";

export interface ContentBatchItem {
  id: number;
  index: number;
  idea_id: number;
  story_job_id: number | null;
  story_version_id: number | null;
  quality_score: number | null;
  status: ContentBatchItemStatus;
  error_message: string | null;
  created_at: string;
}

export interface ContentBatch {
  id: number;
  name: string;
  video_id: number;
  style: string;
  language: string;
  score_threshold: number;
  status: ContentBatchStatus;
  created_at: string;
  completed_at: string | null;
  items: ContentBatchItem[];
}

export interface ContentBatchCreateInput {
  name: string;
  video_id: number;
  idea_ids: number[];
  style: string;
  language?: string;
  score_threshold?: number;
}
