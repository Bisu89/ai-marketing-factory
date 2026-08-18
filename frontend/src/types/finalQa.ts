// Mirrors backend/app/modules/postqa/schemas.py's QAReport/QACheck -- see
// docs/features/54-final-qa.md.

export interface QACheck {
  name: string;
  code: string;
  status: "PASS" | "WARN" | "FAIL";
  severity: "info" | "warning" | "error";
  message: string;
  actual: string | null;
  expected: string | null;
  repair_stage: string | null;
}

export interface QAReport {
  status: "PASS" | "PASS_WITH_WARNINGS" | "FAIL";
  score: number;
  checks: QACheck[];
  project_id: number;
  pipeline_version: string;
  started_at: string;
  completed_at: string;
}

export interface FinalQaResponse {
  project_id: number;
  report: QAReport | null;
}
