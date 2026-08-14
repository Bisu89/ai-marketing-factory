import { apiGet, apiPost } from "./client";
import { config } from "../config/env";
import type { Asset, AssetRegisterInput } from "../types/asset";

export function registerAsset(input: AssetRegisterInput): Promise<Asset> {
  return apiPost("/assets", input);
}

export function searchAssets(query?: string, assetType?: string): Promise<Asset[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (assetType) params.set("asset_type", assetType);
  const qs = params.toString();
  return apiGet(`/assets${qs ? `?${qs}` : ""}`);
}

export function getAsset(assetId: number): Promise<Asset> {
  return apiGet(`/assets/${assetId}`);
}

// Asset.path can point anywhere on disk, so it isn't reachable through the
// /media static mount (mediaUrl() in ./client.ts) -- this hits the
// dedicated GET /assets/{id}/file endpoint instead. Not wrapped in apiGet
// since the caller wants a plain <img>/<video> src URL, not a fetch+JSON
// round trip.
export function assetFileUrl(assetId: number): string {
  return `${config.apiBaseUrl}/assets/${assetId}/file`;
}
