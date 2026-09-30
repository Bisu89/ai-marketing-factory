import { apiPost } from "./client";
import type { GeneratedBeatPlan } from "../types/videoFactory";
import type { QualityMode, QualityReport } from "../types/quality";

// Mirrors backend/app/api/v1/endpoints/quality_gate.py (Task 16 -- see
// docs/features/42-content-quality-gate.md). Deterministic, local-only --
// no AI/LLM call, checked before rendering, never during it.

// Checks whatever plan is currently in the editor, including unsaved
// edits -- the frontend already holds the full BeatPlan shape in memory
// (see buildBeatPlanForSave in VideoFactoryPage.tsx), so there's no need
// to save first just to check readiness.
export function checkPlanQuality(plan: GeneratedBeatPlan, mode: QualityMode = "NORMAL"): Promise<QualityReport> {
  return apiPost("/quality-check", { plan, mode });
}

export function checkProjectQuality(projectId: number, mode: QualityMode = "NORMAL"): Promise<QualityReport> {
  return apiPost(`/projects/${projectId}/quality-check?mode=${mode}`);
}
