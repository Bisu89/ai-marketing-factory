import { config } from "../config/env";
import { apiGet, apiPost } from "./client";

export interface TestVoice {
  id: string;
  label: string;
  language: string;
}

export interface VoiceTestJob {
  status: "running" | "done" | "error";
  error?: string;
  chars?: number;
  words?: number;
  filename?: string;
  path?: string;
  duration_sec?: number;
  elapsed_sec?: number;
}

export function listTestVoices(): Promise<{ default: string; voices: TestVoice[] }> {
  return apiGet("/voice-test/voices");
}

export function startVoiceTest(
  text: string,
  voice: string,
  speed: number,
): Promise<{ job_id: string; chars: number; words: number }> {
  return apiPost("/voice-test/synthesize", { text, voice, speed });
}

export function getVoiceTestJob(jobId: string): Promise<VoiceTestJob> {
  return apiGet(`/voice-test/jobs/${jobId}`);
}

export function voiceTestAudioUrl(jobId: string, download = false): string {
  return `${config.apiBaseUrl}/voice-test/jobs/${jobId}/audio${download ? "?download=1" : ""}`;
}

export interface VoiceTestFile {
  name: string;
  path: string;
  size_kb: number;
  modified: string;
}

export function listVoiceTestFiles(): Promise<{ folder: string; files: VoiceTestFile[] }> {
  return apiGet("/voice-test/files");
}

export function voiceTestFileUrl(name: string, download = false): string {
  return `${config.apiBaseUrl}/voice-test/files/${encodeURIComponent(name)}${download ? "?download=1" : ""}`;
}

export function openVoiceTestFolder(): Promise<{ folder: string }> {
  return apiPost("/voice-test/open-folder");
}
