// Mirrors backend/app/modules/factory/schemas.py's FactoryRunOut exactly
// -- see docs/features/44-one-click-factory-pipeline.md.

export type FactoryRunStatus =
  | "DRAFT"
  | "PREPARING"
  | "GENERATING_BEATS"
  | "PREPARING_VISUALS"
  | "ASSIGNING_ASSETS"
  | "QUALITY_CHECK"
  | "NEEDS_REVIEW"
  | "READY_TO_RENDER"
  | "QUEUED"
  | "RENDERING"
  // Task 27 -- see docs/features/53-thumbnail-metadata-package.md.
  // final.mp4 -> thumbnail.jpg + metadata.json, right before COMPLETED.
  | "PACKAGING"
  // Task 28 -- see docs/features/54-final-qa.md. A read-only re-verification
  // of the finished package; a FAIL routes back to NEEDS_REVIEW (see
  // failed_stage === "FINAL_QA") instead of COMPLETED.
  | "FINAL_QA"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface FactoryRun {
  id: number;
  project_id: number;
  status: FactoryRunStatus;
  failed_stage: string | null;
  error_code: string | null;
  error_message: string | null;
  render_job_id: number | null;
  quality_status: string | null;
  quality_score: number | null;
  qa_status: string | null;
  qa_score: number | null;
  // Task 59 -- "Generate Full by AI": only ever non-null when this run's
  // project used visual_generation.mode === "ai_generated" (the default
  // "library" mode leaves both null, never 0).
  visual_generation_image_count: number | null;
  visual_generation_cost_usd: number | null;
  requires_human_review: boolean;
  review_reason_count: number;
  metrics: Record<string, number>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// The ordered checklist stages a Production Progress UI shows -- distinct
// from FactoryRunStatus itself (NEEDS_REVIEW/FAILED/CANCELLED are outcomes
// overlaid on top of this list, not steps in it).
export const PRODUCTION_STEPS = ["Script", "Beats", "Visuals", "Quality", "Render", "Complete"] as const;
export type ProductionStep = (typeof PRODUCTION_STEPS)[number];

const STEP_FOR_STATUS: Record<FactoryRunStatus, number> = {
  DRAFT: 0,
  PREPARING: 0,
  GENERATING_BEATS: 1,
  PREPARING_VISUALS: 2,
  ASSIGNING_ASSETS: 2,
  QUALITY_CHECK: 3,
  NEEDS_REVIEW: 3,
  READY_TO_RENDER: 4,
  QUEUED: 4,
  RENDERING: 4,
  // Task 27/28 -- grouped with the "Render" step rather than adding a 7th/8th
  // checklist entry; the dedicated Ready-to-Post section (VideoFactoryPage)
  // is where a completed package (and its QA outcome) is actually shown in
  // detail.
  PACKAGING: 4,
  FINAL_QA: 4,
  COMPLETED: 5,
  FAILED: -1,
  CANCELLED: -1,
};

// Index into PRODUCTION_STEPS of the step this status corresponds to, or
// -1 for FAILED/CANCELLED (no single step "owns" those -- see
// FactoryRun.failed_stage for where it actually stopped).
export function stepIndexForStatus(status: FactoryRunStatus): number {
  return STEP_FOR_STATUS[status];
}

export function isActiveFactoryRun(status: FactoryRunStatus): boolean {
  // READY_TO_RENDER is also a stopping point for polling purposes -- it
  // only happens when this project's factory config has
  // render_after_quality_pass=false, and nothing further changes without
  // an explicit user action (the existing Render step, not the factory).
  return !["COMPLETED", "FAILED", "CANCELLED", "NEEDS_REVIEW", "READY_TO_RENDER"].includes(status);
}
