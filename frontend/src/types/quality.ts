// Mirrors backend/app/modules/quality/schemas.py (Task 16 -- see
// docs/features/42-content-quality-gate.md). A deterministic, local-only
// production-readiness heuristic -- never a virality/performance
// prediction (see QualityReport.score's own docstring on the backend).

export type QualityIssueSeverity = "error" | "warning";
export type ReadinessStatus = "READY" | "NEEDS_REVIEW" | "BLOCKED";
export type QualityMode = "NORMAL" | "STRICT";

export interface QualityIssue {
  code: string;
  severity: QualityIssueSeverity;
  message: string;
  beat_id: string | null;
}

export interface VisualCoverageMetrics {
  coverage: number; // 0.0-1.0
  high_confidence: number;
  medium_confidence: number;
  low_confidence: number;
  missing: number;
}

export interface QualityDimensions {
  narrative: number;
  pacing: number;
  visual: number;
  motion: number;
  audio: number;
  captions: number;
}

export interface QualityReport {
  status: ReadinessStatus;
  score: number;
  dimensions: QualityDimensions;
  issues: QualityIssue[]; // severity == "error" -- the blockers
  warnings: QualityIssue[]; // severity == "warning" -- non-blocking in NORMAL mode
  visual: VisualCoverageMetrics;
  metrics: Record<string, unknown>;
}

export const DIMENSION_LABELS: Record<keyof QualityDimensions, string> = {
  narrative: "Narrative",
  pacing: "Pacing",
  visual: "Visual",
  motion: "Motion",
  audio: "Audio",
  captions: "Captions",
};

// -- Batch quality summary (section 31/32) -----------------------------

export interface BatchItemQuality {
  item_id: number;
  project_id: number | null;
  status: string; // READY | NEEDS_REVIEW | BLOCKED | NOT_READY
  score: number | null;
  issues: QualityIssue[];
  warnings: QualityIssue[];
}

export interface BatchQualitySummary {
  batch_id: number;
  ready: number;
  needs_review: number;
  blocked: number;
  items: BatchItemQuality[];
}
