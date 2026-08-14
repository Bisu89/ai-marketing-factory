import { apiPost } from "./client";
import type { VideoComposeJob } from "../types/videoComposer";
import type { CompositionPlan } from "../types/videoFactory";

export interface CompositionRenderRequest {
  plan: CompositionPlan;
  asset_paths: Record<number, string>;
  title: string;
  output_dir?: string | null;
  narration_asset_paths?: Record<number, string>;
  // Names an app.core.render_profile.RenderProfile (see that module) --
  // "SOCIAL_VERTICAL" (default) or "PREVIEW". Validated server-side;
  // recorded on the job for reporting. Does not override each Scene's own
  // output_format (see render_composition's docstring).
  profile?: string;
}

// Mirrors backend/app/api/v1/endpoints/composition_render.py's
// POST /video-compose-jobs/from-composition -- the one endpoint this
// feature's render step calls. It returns an ordinary VideoComposeJob,
// pollable via the existing getVideoComposeJob (api/videoComposer.ts).
export function renderComposition(request: CompositionRenderRequest): Promise<VideoComposeJob> {
  return apiPost("/video-compose-jobs/from-composition", request);
}
