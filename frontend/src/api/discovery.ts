import { apiDelete, apiGet, apiPost } from "./client";
import type {
  FindSimilarResponse,
  RadarPlatform,
  RadarSearch,
  RadarSort,
  SavedRadarResult,
} from "../types/discovery";

export interface RunSearchParams {
  query: string;
  platforms?: RadarPlatform[] | null;
  sort?: RadarSort;
  max_age_days?: number | null;
}

export async function runSearch(params: RunSearchParams): Promise<RadarSearch> {
  return apiPost<RadarSearch>("/discover", {
    query: params.query,
    platforms: params.platforms ?? null,
    sort: params.sort ?? "best",
    max_age_days: params.max_age_days ?? 365,
  });
}

export async function getSearch(id: number): Promise<RadarSearch> {
  return apiGet<RadarSearch>(`/discover/${id}`);
}

export async function listCollections(): Promise<string[]> {
  return apiGet<string[]>("/discover/collections");
}

export async function listSaved(): Promise<SavedRadarResult[]> {
  return apiGet<SavedRadarResult[]>("/discover/saved");
}

export async function saveResult(
  resultId: number,
  collection: string,
  notes?: string | null,
): Promise<void> {
  await apiPost(`/discover/results/${resultId}/save`, { collection, notes: notes ?? null });
}

export async function unsaveResult(resultId: number): Promise<void> {
  await apiDelete(`/discover/results/${resultId}/save`);
}

export async function findSimilar(resultId: number): Promise<FindSimilarResponse> {
  return apiPost<FindSimilarResponse>(`/discover/results/${resultId}/find-similar`);
}
