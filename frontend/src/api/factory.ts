import { apiGet, apiPost } from "./client";
import type { FactoryRun } from "../types/factory";

// Mirrors app/api/v1/endpoints/factory_pipeline.py -- see
// docs/features/44-one-click-factory-pipeline.md.

export function startFactoryRun(projectId: number, force = false): Promise<FactoryRun> {
  return apiPost(`/projects/${projectId}/factory-run${force ? "?force=true" : ""}`);
}

export function getLatestFactoryRun(projectId: number): Promise<FactoryRun | null> {
  return apiGet(`/projects/${projectId}/factory-run`);
}

export function getFactoryRun(runId: number): Promise<FactoryRun> {
  return apiGet(`/factory-runs/${runId}`);
}

export function cancelFactoryRun(runId: number): Promise<FactoryRun> {
  return apiPost(`/factory-runs/${runId}/cancel`);
}

export function retryFactoryRun(runId: number): Promise<FactoryRun> {
  return apiPost(`/factory-runs/${runId}/retry`);
}

export function continueFactoryRun(runId: number, force = false): Promise<FactoryRun> {
  return apiPost(`/factory-runs/${runId}/continue${force ? "?force=true" : ""}`);
}
