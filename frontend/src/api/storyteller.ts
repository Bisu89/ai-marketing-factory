import { apiDelete, apiGet, apiPost, apiUpload } from "./client";
import { config } from "../config/env";
import type { CreateEpisodeInput, StorytellerAsset, StorytellerAssetKind, StorytellerEpisode } from "../types/storyteller";

export function listEpisodes(): Promise<StorytellerEpisode[]> {
  return apiGet("/storyteller/episodes");
}

export function getEpisode(id: number): Promise<StorytellerEpisode> {
  return apiGet(`/storyteller/episodes/${id}`);
}

export function createEpisode(input: CreateEpisodeInput): Promise<StorytellerEpisode> {
  return apiPost("/storyteller/episodes", input);
}

export function createEpisodeFromFile(
  file: File,
  fields: { title: string; burn_captions: boolean; background_asset_id?: number | null; avatar_asset_id?: number | null },
): Promise<StorytellerEpisode> {
  const form = new FormData();
  form.set("file", file);
  form.set("title", fields.title);
  form.set("burn_captions", String(fields.burn_captions));
  if (fields.background_asset_id != null) form.set("background_asset_id", String(fields.background_asset_id));
  if (fields.avatar_asset_id != null) form.set("avatar_asset_id", String(fields.avatar_asset_id));
  return apiUpload("/storyteller/episodes/upload", form);
}

export function retryEpisode(id: number): Promise<StorytellerEpisode> {
  return apiPost(`/storyteller/episodes/${id}/retry`);
}

export function deleteEpisode(id: number): Promise<void> {
  return apiDelete(`/storyteller/episodes/${id}`);
}

export function episodeFileUrl(id: number): string {
  return `${config.apiBaseUrl}/storyteller/episodes/${id}/file`;
}

export function listAssets(kind?: StorytellerAssetKind): Promise<StorytellerAsset[]> {
  return apiGet(`/storyteller/assets${kind ? `?kind=${kind}` : ""}`);
}

export function uploadAsset(kind: StorytellerAssetKind, name: string, file: File): Promise<StorytellerAsset> {
  const form = new FormData();
  form.set("kind", kind);
  form.set("name", name);
  form.set("file", file);
  return apiUpload("/storyteller/assets", form);
}

export function deleteAsset(id: number): Promise<void> {
  return apiDelete(`/storyteller/assets/${id}`);
}
