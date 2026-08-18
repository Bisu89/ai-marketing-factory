import { apiGet, apiPost } from "./client";
import type { FinalQaResponse } from "../types/finalQa";

// Mirrors app/api/v1/endpoints/final_qa.py -- see docs/features/54-final-qa.md.

export function getProjectFinalQa(projectId: number): Promise<FinalQaResponse> {
  return apiGet(`/projects/${projectId}/final-qa`);
}

export function regenerateFinalQa(projectId: number): Promise<FinalQaResponse> {
  return apiPost(`/projects/${projectId}/regenerate-final-qa`);
}
