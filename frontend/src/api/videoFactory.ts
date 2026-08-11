import { apiPost } from "./client";
import type { VideoComposeJob } from "../types/videoComposer";
import type { CompositionPlan } from "../types/videoFactory";

export interface CompositionRenderRequest {
  plan: CompositionPlan;
  asset_paths: Record<number, string>;
  title: string;
  output_dir?: string | null;
}

// Mirrors backend/app/api/v1/endpoints/composition_render.py's
// POST /video-compose-jobs/from-composition -- the one endpoint this
// feature's render step calls. It returns an ordinary VideoComposeJob,
// pollable via the existing getVideoComposeJob (api/videoComposer.ts).
export function renderComposition(request: CompositionRenderRequest): Promise<VideoComposeJob> {
  return apiPost("/video-compose-jobs/from-composition", request);
}
