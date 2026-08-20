import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type {
  AffiliateKPI,
  AffiliateLink,
  AffiliateProduct,
  AffiliateProductCreate,
  ProductMatch,
} from "../types/affiliate";

export function getProducts(params: { category?: string; active_only?: boolean } = {}): Promise<AffiliateProduct[]> {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  if (params.active_only) query.set("active_only", "true");
  const qs = query.toString();
  return apiGet(`/affiliate/products${qs ? `?${qs}` : ""}`);
}

export function createProduct(payload: AffiliateProductCreate): Promise<AffiliateProduct> {
  return apiPost("/affiliate/products", payload);
}

export function updateProduct(id: number, payload: Partial<AffiliateProductCreate>): Promise<AffiliateProduct> {
  return apiPatch(`/affiliate/products/${id}`, payload);
}

export function deleteProduct(id: number): Promise<void> {
  return apiDelete(`/affiliate/products/${id}`);
}

export function recomputeProductScore(id: number): Promise<AffiliateProduct> {
  return apiPost(`/affiliate/products/${id}/recompute-score`);
}

export function getLinks(productId: number): Promise<AffiliateLink[]> {
  return apiGet(`/affiliate/products/${productId}/links`);
}

export function createLink(productId: number, label: string | null): Promise<AffiliateLink> {
  return apiPost(`/affiliate/products/${productId}/links`, { label });
}

export function deleteLink(id: number): Promise<void> {
  return apiDelete(`/affiliate/links/${id}`);
}

export function recommendProducts(params: { story_text?: string; content_idea_id?: number; limit?: number }): Promise<ProductMatch[]> {
  const query = new URLSearchParams();
  if (params.story_text) query.set("story_text", params.story_text);
  if (params.content_idea_id != null) query.set("content_idea_id", String(params.content_idea_id));
  if (params.limit) query.set("limit", String(params.limit));
  return apiPost(`/affiliate/recommend-products?${query.toString()}`);
}

export function getAffiliateKpi(): Promise<AffiliateKPI> {
  return apiGet("/affiliate/kpi");
}
