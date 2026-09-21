import { apiDelete, apiGet, apiPost, apiUpload } from "./client";
import { config } from "../config/env";
import type {
  CreateEpisodeInput,
  StorytellerAsset,
  StorytellerAssetKind,
  StorytellerEpisode,
  StorytellerLayout,
} from "../types/storyteller";

export function listEpisodes(): Promise<StorytellerEpisode[]> {
  return apiGet("/storyteller/episodes");
}

export function getEpisode(id: number): Promise<StorytellerEpisode> {
  return apiGet(`/storyteller/episodes/${id}`);
}

export function createEpisode(input: CreateEpisodeInput): Promise<StorytellerEpisode> {
  return apiPost("/storyteller/episodes", input);
}

export interface EpisodeFileFields {
  title: string;
  voice: string;
  narration_rate: string;
  burn_captions: boolean;
  layout: StorytellerLayout;
  background_asset_id?: number | null;
  avatar_asset_id?: number | null;
  left_asset_id?: number | null;
  middle_asset_id?: number | null;
  right_asset_id?: number | null;
  slide_asset_ids?: number[] | null;
  music_asset_id?: number | null;
  disclaimer_text?: string | null;
  story_title?: string | null;
  story_author?: string | null;
  story_character?: string | null;
}

export function createEpisodeFromFile(file: File, fields: EpisodeFileFields): Promise<StorytellerEpisode> {
  const form = new FormData();
  form.set("file", file);
  form.set("title", fields.title);
  form.set("voice", fields.voice);
  form.set("narration_rate", fields.narration_rate);
  form.set("burn_captions", String(fields.burn_captions));
  form.set("layout", fields.layout);
  if (fields.slide_asset_ids && fields.slide_asset_ids.length > 0) {
    form.set("slide_asset_ids", fields.slide_asset_ids.join(","));
  }
  const optional: [string, string | number | null | undefined][] = [
    ["background_asset_id", fields.background_asset_id],
    ["avatar_asset_id", fields.avatar_asset_id],
    ["left_asset_id", fields.left_asset_id],
    ["middle_asset_id", fields.middle_asset_id],
    ["right_asset_id", fields.right_asset_id],
    ["music_asset_id", fields.music_asset_id],
    ["disclaimer_text", fields.disclaimer_text],
    ["story_title", fields.story_title],
    ["story_author", fields.story_author],
    ["story_character", fields.story_character],
  ];
  for (const [key, value] of optional) {
    if (value != null && value !== "") form.set(key, String(value));
  }
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
