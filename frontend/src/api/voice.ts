import { apiGet, apiPost } from "./client";

// Mirrors backend/app/api/v1/endpoints/voice_generate.py (Task 22 -- see
// docs/features/48-voice-factory-local-tts.md). Real, installed SAPI5
// voices -- never a hardcoded list (what's available depends on the end
// user's own Windows installation).
export interface LocalVoiceOption {
  id: string;
  name: string;
  languages: string[];
}

export function listLocalVoices(): Promise<LocalVoiceOption[]> {
  return apiGet("/voice/providers/local/voices");
}

export function regenerateVoice(projectId: number): Promise<{ project_id: number }> {
  return apiPost(`/projects/${projectId}/regenerate-voice`, {});
}
