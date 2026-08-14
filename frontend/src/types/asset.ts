// Mirrors backend/app/modules/asset/schemas.py (AssetOut, AssetRegisterIn,
// AssetImportRequest, AssetImportJobOut, RescanResult). Task 15 (see
// docs/features/41-local-asset-ingestion.md) added the ingestion-derived
// fields below plus the import-job/rescan shapes.

export type AssetType = "image" | "video" | "audio";

export type AssetOrientation = "PORTRAIT" | "LANDSCAPE" | "SQUARE";
export type AssetStatus = "ACTIVE" | "MISSING" | "INVALID";
export type PortraitSuitability = "EXCELLENT" | "GOOD" | "CROP_REQUIRED" | "LOW_RESOLUTION";

export interface Asset {
  id: number;
  filename: string;
  path: string;
  type: AssetType;
  width: number | null;
  height: number | null;
  duration_sec: number | null;
  filesize_bytes: number | null;
  tags: string[];
  source: string;
  source_ref: string | null;
  extra_metadata: Record<string, unknown> | null;
  is_ready: boolean;
  created_at: string;

  // -- Task 15 --
  content_hash: string | null;
  orientation: AssetOrientation | null;
  category: string | null;
  emotion: string | null;
  status: AssetStatus;
  thumbnail_path: string | null;
  aspect_ratio: number | null;
  portrait_suitability: PortraitSuitability | null;
}

export interface AssetRegisterInput {
  filename: string;
  path: string;
  type: AssetType;
  width?: number;
  height?: number;
  duration_sec?: number;
  tags?: string[];
  source?: string;
  source_ref?: string | null;
  extra_metadata?: Record<string, unknown> | null;
}

// -- Bulk local import (Task 15) --------------------------------------------

export interface AssetImportRequest {
  paths?: string[];
  folder?: string;
  recursive?: boolean;
}

export type AssetImportJobStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "CANCELLED" | "FAILED";

export interface FailedImportFile {
  path: string;
  reason: string;
}

export interface AssetImportJob {
  id: number;
  status: AssetImportJobStatus;
  source_label: string;
  total_files: number;
  processed_files: number;
  imported_count: number;
  duplicate_count: number;
  failed_count: number;
  current_file: string | null;
  failed_files: FailedImportFile[];
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface RescanResult {
  checked: number;
  now_missing: number;
  now_active: number;
  now_invalid: number;
  unchanged: number;
}
