import { apiGet, apiUpload } from "./client";
import type {
  InsightPost,
  InsightSummary,
  InsightUploadSummary,
  PostTypeBreakdown,
  TrendPoint,
} from "../types/insight";

export async function uploadInsightCsv(file: File): Promise<InsightUploadSummary> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<InsightUploadSummary>("/insights/upload", formData);
}

export async function listUploads(): Promise<InsightUploadSummary[]> {
  return apiGet<InsightUploadSummary[]>("/insights/uploads");
}

export async function getSummary(uploadId?: number): Promise<InsightSummary> {
  const query = uploadId ? `?upload_id=${uploadId}` : "";
  return apiGet<InsightSummary>(`/insights/summary${query}`);
}

export async function getTopPosts(
  uploadId?: number,
  sort: "views" | "interactions" = "views",
  limit = 20,
): Promise<InsightPost[]> {
  const params = new URLSearchParams({ sort, limit: String(limit) });
  if (uploadId) params.set("upload_id", String(uploadId));
  return apiGet<InsightPost[]>(`/insights/posts?${params.toString()}`);
}

export async function getByPostType(uploadId?: number): Promise<PostTypeBreakdown[]> {
  const query = uploadId ? `?upload_id=${uploadId}` : "";
  return apiGet<PostTypeBreakdown[]>(`/insights/by-post-type${query}`);
}

export async function getTrend(): Promise<TrendPoint[]> {
  return apiGet<TrendPoint[]>("/insights/trend");
}
