export type RadarPlatform = "reddit" | "youtube" | "tiktok" | "instagram";
export type RadarSort = "best" | "newest" | "most_viewed";

export interface ScoreBreakdown {
  relevance: number;
  engagement: number;
  recency: number;
  short_form: number;
  content_signals: number;
}

export interface RadarResult {
  id: number;
  platform: RadarPlatform;
  source_url: string;
  title: string;
  description: string | null;
  thumbnail_url: string | null;
  creator_name: string | null;
  creator_url: string | null;
  published_at: string | null;
  duration_sec: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  width: number | null;
  height: number | null;
  aspect_ratio: number | null;
  content_tags: string[];
  also_on: RadarPlatform[];
  viral_score: number;
  score_breakdown: ScoreBreakdown;
  rights_status: string;
  attribution: string | null;
  download_capability: "ALLOWED" | "PERMISSION_REQUIRED" | "UNSUPPORTED";
  saved_video_id: number | null;
  collection: string | null;
  notes: string | null;
}

export interface EngineStatus {
  platform: RadarPlatform;
  status: "ok" | "unavailable" | "error";
  result_count: number;
  error: string | null;
}

export interface RadarSearch {
  id: number;
  query: string;
  normalized_query: string;
  expanded_queries: string[];
  engine_statuses: EngineStatus[];
  total_before_dedup: number;
  unique_count: number;
  results: RadarResult[];
  created_at: string;
}

export interface SavedRadarResult extends RadarResult {
  search_id: number;
  query: string;
  discovered_at: string;
}

export interface FindSimilarResponse {
  keywords: string[];
  search: RadarSearch;
}
