import { apiGet, apiPost, apiPut } from "./client";
import type { BeatPreviewRequest, BeatPreviewResult, GeneratedBeatPlan, Project } from "../types/videoFactory";

// Mirrors backend/app/api/v1/endpoints/beat_generate.py's
// POST /beats/generate -- see docs/features/30-generate-beats.md.
export function generateBeatPlan(script: string): Promise<GeneratedBeatPlan> {
  return apiPost("/beats/generate", { script });
}

// Mirrors backend/app/modules/beat/router.py's GET/PUT /beat-plan -- the
// single current Video Factory draft, persisted as beats.json. GET returns
// null (not a 404) when nothing has been saved yet -- see
// docs/features/31-beat-editor-crud-persistence.md.
export function loadBeatPlan(): Promise<GeneratedBeatPlan | null> {
  return apiGet<GeneratedBeatPlan | null>("/beat-plan");
}

export function saveBeatPlan(plan: GeneratedBeatPlan): Promise<GeneratedBeatPlan> {
  return apiPut<GeneratedBeatPlan>("/beat-plan", plan);
}

// Mirrors backend/app/api/v1/endpoints/beat_preview.py's POST /beats/preview
// -- a real, synchronous, single-clip ffmpeg render (see
// docs/features/34-local-motion-renderer.md), not a mocked/CSS preview.
export function renderBeatPreview(request: BeatPreviewRequest): Promise<BeatPreviewResult> {
  return apiPost("/beats/preview", request);
}

// Mirrors backend/app/modules/beat/router.py's GET/PUT /projects/{id} (Task
// 13) -- the real, independently-addressable multi-project store batch
// creation needs, separate from loadBeatPlan/saveBeatPlan's single
// "current" beats.json above. See docs/features/40-batch-video-creation.md
// and types/videoFactory.ts's Project type.
export function getProject(projectId: number): Promise<Project> {
  return apiGet(`/projects/${projectId}`);
}

// Task 18 -- see docs/features/44-one-click-factory-pipeline.md. A single-
// project counterpart to createBatch (api/batch.ts): a real, id-addressable
// Project row outside of a batch, needed so the "New Video" one-click flow
// has something to attach a FactoryRun to (the classic loadBeatPlan/
// saveBeatPlan singleton above has no id at all).
// Task 21 -- see docs/features/47-content-brief-script-engine.md. Exactly
// one of script_text/idea must be provided; the backend validates this
// (400 if both are blank).
export interface CreateProjectRequest {
  name: string;
  script_text?: string | null;
  idea?: string | null;
  template_id: string;
}

export function createProject(request: CreateProjectRequest): Promise<Project> {
  return apiPost("/projects", request);
}

export function saveProjectBeatPlan(projectId: number, plan: GeneratedBeatPlan): Promise<GeneratedBeatPlan> {
  return apiPut(`/projects/${projectId}/beat-plan`, plan);
}
