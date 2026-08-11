import { apiGet, apiPost } from "./client";
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
