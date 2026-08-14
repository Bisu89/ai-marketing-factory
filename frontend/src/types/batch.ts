// Mirrors backend/app/modules/batch/schemas.py exactly -- see
// docs/features/40-batch-video-creation.md. Batch/BatchItem are a real,
// separate DB-backed system alongside the single-project beats.json flow
// (see types/videoFactory.ts's Project type) -- created only via "Batch
// Create", never auto-rendered.

export type BatchStatus = "DRAFT" | "PROCESSING" | "COMPLETED" | "PARTIAL_FAILURE" | "FAILED" | "CANCELLED";

// Mirrors backend/app/modules/batch/models.py's BATCH_ITEM_STATUSES (9
// values) exactly. "READY_TO_RENDER" is part of the contract's own status
// vocabulary but the backend never stores it as a literal transition --
// eligibility for a BEATS_READY item is computed fresh on every
// GET /batches/{id} instead (see BatchItem.eligible below).
export type BatchItemStatus =
  | "PENDING"
  | "PROJECT_CREATED"
  | "BEATS_READY"
  | "READY_TO_RENDER"
  // Task 16 (see docs/features/42-content-quality-gate.md) -- the Quality
  // Gate looked at this item during "Render All" and returned NEEDS_REVIEW
  // (real, non-blocking issues, but not READY either); this batch's
  // default policy skips rendering it until a human reviews it.
  | "NEEDS_REVIEW"
  | "RENDERING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED"
  | "CANCELLED";

export interface BatchItem {
  id: number;
  index: number;
  script_text: string;
  project_id: number | null;
  status: BatchItemStatus;
  error_message: string | null;
  render_job_id: number | null;
  // Only populated (non-null) for BEATS_READY items by the real
  // GET /batches/{id} detail endpoint (it needs to resolve assets) --
  // always null from the plain GET /batches list view. Recomputed fresh
  // every time, never a stored/stale flag.
  eligible: boolean | null;
  ineligible_reason: string | null;
  // Task 16 -- same "computed fresh, None outside GET /batches/{id}" shape
  // as eligible/ineligible_reason above.
  quality_status: string | null;
  quality_score: number | null;
}

export interface Batch {
  id: number;
  name: string;
  template_id: string | null;
  status: BatchStatus;
  items: BatchItem[];
}

export interface CreateBatchRequest {
  name: string;
  template_id: string;
  scripts_text: string;
}

export interface BatchPreviewItem {
  index: number;
  project_name: string;
  script_preview: string;
}

export interface BatchPreview {
  template_id: string;
  script_count: number;
  items: BatchPreviewItem[];
}
