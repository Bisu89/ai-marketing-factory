import { apiDelete, apiGet, apiPost } from "./client";
import type { CompetitorVideo, CompetitorVideoCreate, TikTokAccount, TikTokVideo } from "../types/competitorIntelligence";

export function getTikTokAuthorizeUrl(): Promise<{ authorize_url: string }> {
  return apiGet("/tiktok/oauth/authorize-url");
}

export function getTikTokAccount(): Promise<TikTokAccount | null> {
  return apiGet("/tiktok/account");
}

export function disconnectTikTokAccount(): Promise<{ disconnected: boolean }> {
  return apiDelete("/tiktok/account");
}

export function triggerTikTokSync(): Promise<{ started: boolean; already_syncing: boolean }> {
  return apiPost("/tiktok/sync");
}

export function getTikTokVideos(): Promise<TikTokVideo[]> {
  return apiGet("/tiktok/videos");
}

export function createCompetitorVideo(payload: CompetitorVideoCreate): Promise<CompetitorVideo> {
  return apiPost("/competitor-videos", payload);
}

export function getCompetitorVideos(): Promise<CompetitorVideo[]> {
  return apiGet("/competitor-videos");
}

export function deleteCompetitorVideo(id: number): Promise<{ deleted: boolean }> {
  return apiDelete(`/competitor-videos/${id}`);
}

export function analyzeCompetitorVideo(id: number): Promise<CompetitorVideo> {
  return apiPost(`/competitor-videos/${id}/analyze`);
}
