export interface InsightUploadSummary {
  id: number;
  filename: string;
  row_count: number;
  uploaded_at: string;
  skipped_rows?: number;
}

export interface InsightSummary {
  total_posts: number;
  total_views: number;
  total_viewers: number;
  total_interactions: number;
  total_comments: number;
  total_shares: number;
  total_saves: number;
  total_reactions: number;
  total_impressions: number;
  avg_retention_pct: number | null;
}

export interface InsightPost {
  post_id: string;
  title: string;
  post_type: string | null;
  permalink: string | null;
  posted_at: string | null;
  duration_sec: number | null;
  views: number;
  viewers: number;
  interactions: number;
  comments: number;
  shares: number;
  saves: number;
  reactions: number;
  retention_pct: number | null;
}

export interface PostTypeBreakdown {
  post_type: string;
  post_count: number;
  total_views: number;
  avg_views: number;
  avg_retention_pct: number | null;
}

export interface TrendPoint {
  upload_id: number;
  uploaded_at: string;
  filename: string;
  total_views: number;
  total_interactions: number;
}
