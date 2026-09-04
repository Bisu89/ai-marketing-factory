import { apiGet, apiPut } from "./client";
import type { AIProvider, AppSettings, BrowseFoldersResult } from "../types/settings";

export async function getSettings(): Promise<AppSettings> {
  return apiGet<AppSettings>("/settings");
}

export async function updateLibraryDir(path: string): Promise<{ library_dir: string }> {
  return apiPut<{ library_dir: string }>("/settings/library-dir", { path });
}

export async function updateAnthropicApiKey(apiKey: string): Promise<{ has_anthropic_key: boolean }> {
  return apiPut<{ has_anthropic_key: boolean }>("/settings/anthropic-key", { api_key: apiKey });
}

export async function updateOpenAiApiKey(apiKey: string): Promise<{ has_openai_key: boolean }> {
  return apiPut<{ has_openai_key: boolean }>("/settings/openai-key", { api_key: apiKey });
}

export async function updateAiProvider(provider: AIProvider): Promise<{ ai_provider: AIProvider }> {
  return apiPut<{ ai_provider: AIProvider }>("/settings/ai-provider", { provider });
}

export async function updateTikTokClientKey(clientKey: string): Promise<{ has_tiktok_client_key: boolean }> {
  return apiPut<{ has_tiktok_client_key: boolean }>("/settings/tiktok-client-key", { client_key: clientKey });
}

export async function updateTikTokClientSecret(clientSecret: string): Promise<{ has_tiktok_client_secret: boolean }> {
  return apiPut<{ has_tiktok_client_secret: boolean }>("/settings/tiktok-client-secret", { client_secret: clientSecret });
}

export async function updateTikTokRedirectUri(redirectUri: string): Promise<{ tiktok_redirect_uri: string }> {
  return apiPut<{ tiktok_redirect_uri: string }>("/settings/tiktok-redirect-uri", { redirect_uri: redirectUri });
}

export async function updateRenderCacheRetention(
  days: number,
): Promise<{ render_cache_retention_days: number }> {
  return apiPut<{ render_cache_retention_days: number }>("/settings/render-cache-retention", { days });
}

export async function updateGoogleOAuthClient(
  clientId: string,
  clientSecret: string,
): Promise<{ has_google_oauth_client: boolean }> {
  return apiPut<{ has_google_oauth_client: boolean }>("/settings/google-oauth-client", {
    client_id: clientId,
    client_secret: clientSecret,
  });
}

export async function updateNewsPollInterval(
  minutes: number,
): Promise<{ news_poll_interval_minutes: number }> {
  return apiPut<{ news_poll_interval_minutes: number }>("/settings/news-poll-interval", { minutes });
}

export interface DefaultVoiceResult {
  default_voice_provider: "local" | "edge_tts";
  default_voice_id: string;
  default_voice_speed: number;
  default_sentence_pause_sec: number;
}

export async function updateDefaultVoice(input: {
  provider: "local" | "edge_tts";
  voice_id: string;
  speed: number;
  sentence_pause_sec: number;
}): Promise<DefaultVoiceResult> {
  return apiPut<DefaultVoiceResult>("/settings/default-voice", input);
}

export async function browseFolders(path?: string): Promise<BrowseFoldersResult> {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return apiGet<BrowseFoldersResult>(`/settings/browse-folders${query}`);
}
