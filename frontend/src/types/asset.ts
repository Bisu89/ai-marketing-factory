// Mirrors backend/app/modules/asset/schemas.py (AssetOut, AssetRegisterIn).

export type AssetType = "image" | "video" | "audio";

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
