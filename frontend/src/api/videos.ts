import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type { CategoryOut, VideoListParams, VideoListResponse, VideoOut } from "../features/library/types";

function buildQuery(params: VideoListParams): string {
  const search = new URLSearchParams();
  search.set("page", String(params.page));
  search.set("page_size", String(params.page_size));
  search.set("sort", params.sort);
  if (params.search) search.set("search", params.search);
  if (params.platform) search.set("platform", params.platform);
  if (params.status) search.set("status", params.status);
  if (params.category_id != null) search.set("category_id", String(params.category_id));
  if (params.tag) search.set("tag", params.tag);
  if (params.favorite != null) search.set("favorite", String(params.favorite));
  if (params.duration) search.set("duration", params.duration);
  if (params.resolution) search.set("resolution", params.resolution);
  return search.toString();
}

export function fetchVideos(params: VideoListParams): Promise<VideoListResponse> {
  return apiGet(`/videos?${buildQuery(params)}`);
}

export function fetchCategories(): Promise<CategoryOut[]> {
  return apiGet(`/categories`);
}

export function setFavorite(videoId: number, favorite: boolean): Promise<VideoOut> {
  return favorite ? apiPost(`/videos/${videoId}/favorite`) : apiDelete(`/videos/${videoId}/favorite`);
}

export function openFolder(videoId: number): Promise<void> {
  return apiPost(`/videos/${videoId}/open-folder`);
}

export function updateVideo(
  videoId: number,
  patch: { status?: string; category_id?: number; notes?: string },
): Promise<VideoOut> {
  return apiPut(`/videos/${videoId}`, patch);
}
