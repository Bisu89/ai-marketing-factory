import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type { Batch } from "../types/batch";
import type {
  DraftScriptsResponse,
  FetchAllResponse,
  FetchResult,
  NewsItemListResponse,
  NewsItemStatus,
  NewsSource,
  NewsSourceCreateInput,
  NewsSourceUpdateInput,
} from "../types/news";

export function fetchNewsSources(): Promise<NewsSource[]> {
  return apiGet("/news/sources");
}

export function createNewsSource(input: NewsSourceCreateInput): Promise<NewsSource> {
  return apiPost("/news/sources", input);
}

export function updateNewsSource(id: number, patch: NewsSourceUpdateInput): Promise<NewsSource> {
  return apiPatch(`/news/sources/${id}`, patch);
}

export function deleteNewsSource(id: number): Promise<void> {
  return apiDelete(`/news/sources/${id}`);
}

export function fetchNewsSource(id: number): Promise<FetchResult> {
  return apiPost(`/news/sources/${id}/fetch`);
}

export function fetchAllNewsSources(): Promise<FetchAllResponse> {
  return apiPost("/news/fetch-all");
}

export function fetchNewsItems(params: {
  status?: NewsItemStatus;
  source_id?: number;
  page?: number;
  page_size?: number;
}): Promise<NewsItemListResponse> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.source_id != null) search.set("source_id", String(params.source_id));
  search.set("page", String(params.page ?? 1));
  search.set("page_size", String(params.page_size ?? 100));
  return apiGet(`/news/items?${search.toString()}`);
}

export function dismissNewsItem(id: number): Promise<unknown> {
  return apiPatch(`/news/items/${id}`, { status: "dismissed" });
}

export function draftNewsScripts(itemIds: number[]): Promise<DraftScriptsResponse> {
  return apiPost("/news/items/draft-scripts", { item_ids: itemIds });
}

export function createNewsBatch(input: {
  name: string;
  template_id: string;
  item_ids: number[];
}): Promise<Batch> {
  return apiPost("/news/batch", input);
}
