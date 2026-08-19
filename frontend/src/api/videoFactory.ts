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
  // See docs/features/56-classic-render-captions.md -- when this project
  // is a real, id-addressable one (the classic singleton-beats.json flow
  // has no project id at all), the backend resolves/generates a real
  // captions.ass and burns it even for local-voice narration, which
  // previously never got burned captions no matter this checkbox's state.
  project_id?: number;
  captions_enabled?: boolean;
}

// Mirrors backend/app/api/v1/endpoints/composition_render.py's
// POST /video-compose-jobs/from-composition -- the one endpoint this
// feature's render step calls. It returns an ordinary VideoComposeJob,
// pollable via the existing getVideoComposeJob (api/videoComposer.ts).
export function renderComposition(request: CompositionRenderRequest): Promise<VideoComposeJob> {
  return apiPost("/video-compose-jobs/from-composition", request);
}
