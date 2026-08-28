import { apiDelete, apiGet, apiPost } from "./client";
import { config } from "../config/env";
import type { Asset, AssetImportJob, AssetImportRequest, AssetRegisterInput, RescanResult } from "../types/asset";

export function registerAsset(input: AssetRegisterInput): Promise<Asset> {
  return apiPost("/assets", input);
}

export interface SearchAssetsFilters {
  assetType?: string;
  orientation?: string;
  category?: string;
  emotion?: string;
  source?: string;
  missingOnly?: boolean;
}

export function searchAssets(query?: string, assetType?: string, filters?: SearchAssetsFilters): Promise<Asset[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  const resolvedType = filters?.assetType ?? assetType;
  if (resolvedType) params.set("asset_type", resolvedType);
  if (filters?.orientation) params.set("orientation", filters.orientation);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.emotion) params.set("emotion", filters.emotion);
  if (filters?.source) params.set("source", filters.source);
  if (filters?.missingOnly) params.set("missing_only", "true");
  const qs = params.toString();
  return apiGet(`/assets${qs ? `?${qs}` : ""}`);
}

export function getAsset(assetId: number): Promise<Asset> {
  return apiGet(`/assets/${assetId}`);
}

// Unregisters the asset from the library only -- the real file on disk is
// never touched (see backend/app/modules/asset/service.py's own delete()).
export function deleteAsset(assetId: number): Promise<void> {
  return apiDelete(`/assets/${assetId}`);
}

// Asset.path can point anywhere on disk, so it isn't reachable through the
// /media static mount (mediaUrl() in ./client.ts) -- this hits the
// dedicated GET /assets/{id}/file endpoint instead. Not wrapped in apiGet
// since the caller wants a plain <img>/<video> src URL, not a fetch+JSON
// round trip.
export function assetFileUrl(assetId: number): string {
  return `${config.apiBaseUrl}/assets/${assetId}/file`;
}

// Same reasoning as assetFileUrl -- a plain src URL for the small,
// Task-15-generated preview image (library_dir/_asset/thumbnails/<id>.jpg),
// not every asset has one (e.g. one registered before Task 15).
export function assetThumbnailUrl(assetId: number): string {
  return `${config.apiBaseUrl}/assets/${assetId}/thumbnail`;
}

// -- Bulk local import (Task 15 -- see docs/features/41-local-asset-ingestion.md) --

export function importAssets(request: AssetImportRequest): Promise<AssetImportJob> {
  return apiPost("/assets/import", request);
}

export function getAssetImportJob(jobId: number): Promise<AssetImportJob> {
  return apiGet(`/assets/import/${jobId}`);
}

export function cancelAssetImportJob(jobId: number): Promise<AssetImportJob> {
  return apiPost(`/assets/import/${jobId}/cancel`);
}

export function rescanAssets(): Promise<RescanResult> {
  return apiPost("/assets/rescan");
}

// -- Clean up the Factory's own per-beat render cache (voice/motion) --

export interface CleanupGeneratedRequest {
  sources?: string[];
  delete_files?: boolean;
  dry_run?: boolean;
}

export interface CleanupGeneratedResult {
  dry_run: boolean;
  projects_cleaned: number[];
  assets_unregistered: number;
  files_deleted: number;
  bytes_freed: number;
  megabytes_freed: number;
  skipped: {
    no_completed_render: number;
    render_in_progress: number;
    unparseable_path: number;
  };
}

export function cleanupGeneratedAssets(request: CleanupGeneratedRequest = {}): Promise<CleanupGeneratedResult> {
  return apiPost("/assets/cleanup-generated", request);
}
