import { config } from "../config/env";
import { apiGet, apiPost } from "./client";
import type { VideoComposeJob } from "../types/videoComposer";

export interface CreateVideoComposeJobInput {
  title: string;
  script: string;
  files: File[];
  music?: File | null;
  musicVolume: number;
  transitionDuration: number;
  burnSubtitles: boolean;
  outputDir?: string;
}

export async function createVideoComposeJob(input: CreateVideoComposeJobInput): Promise<VideoComposeJob> {
  const form = new FormData();
  form.set("title", input.title);
  form.set("script", input.script);
  form.set("music_volume", String(input.musicVolume));
  form.set("transition_duration", String(input.transitionDuration));
  form.set("burn_subtitles", String(input.burnSubtitles));
  if (input.outputDir) form.set("output_dir", input.outputDir);
  // Order matters -- appended in the exact merge order the user arranged
  // via the reorder buttons, and the backend derives clip position purely
  // from this array order.
  input.files.forEach((file) => form.append("files", file));
  if (input.music) form.set("music", input.music);

  // No Content-Type header on purpose -- the browser sets the multipart
  // boundary itself for a FormData body.
  const response = await fetch(`${config.apiBaseUrl}/video-compose-jobs`, { method: "POST", body: form });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `API request failed: ${response.status}`);
  }
  return response.json();
}

export function listVideoComposeJobs(): Promise<VideoComposeJob[]> {
  return apiGet("/video-compose-jobs");
}

export function openVideoComposeJobFolder(jobId: number): Promise<void> {
  return apiPost(`/video-compose-jobs/${jobId}/open-folder`);
}

export async function pickVideoComposeOutputFolder(): Promise<string | null> {
  const result = await apiPost<{ path: string | null }>("/video-compose-jobs/pick-folder");
  return result.path;
}
