export type PublishLogStatus = "none" | "winner" | "loser" | "archived";

export const PUBLISH_LOG_STATUS_LABELS: Record<PublishLogStatus, string> = {
  none: "Chưa đánh giá",
  winner: "Winner",
  loser: "Loser",
  archived: "Đã lưu trữ",
};

export interface PublishLog {
  id: number;
  video_id: number;
  video_title: string;
  video_topic: string | null;
  video_emotion: string | null;
  platform: string;
  page_name: string | null;
  hook_type: string | null;
  story_style: string | null;
  ai_story_job_id: number | null;
  affiliate_product: string | null;
  affiliate_clicks: number;
  affiliate_sales: number;
  affiliate_revenue: number;
  published_at: string;
  status: PublishLogStatus;
  post_id: string | null;
  page_id: string | null;
  notes: string | null;
  created_at: string;
  views: number | null;
  interactions: number | null;
}

export interface PublishLogCreateInput {
  video_id: number;
  platform?: string;
  page_name?: string;
  hook_type?: string;
  story_style?: string;
  ai_story_job_id?: number;
  affiliate_product?: string;
  affiliate_clicks?: number;
  affiliate_sales?: number;
  affiliate_revenue?: number;
  published_at?: string;
  status?: PublishLogStatus;
  notes?: string;
}

export interface PublishLogUpdateInput {
  page_name?: string;
  hook_type?: string;
  story_style?: string;
  affiliate_product?: string;
  affiliate_clicks?: number;
  affiliate_sales?: number;
  affiliate_revenue?: number;
  status?: PublishLogStatus;
  notes?: string;
}

export interface UnlinkedPost {
  post_id: string;
  page_id: string;
  page_name: string;
  title: string;
  posted_at: string | null;
  views: number;
}

export interface DimensionBreakdown {
  label: string;
  post_count: number;
  total_views: number;
  avg_views: number;
  total_interactions: number;
}

export interface PerformanceOverview {
  by_topic: DimensionBreakdown[];
  by_emotion: DimensionBreakdown[];
  by_hook_type: DimensionBreakdown[];
  by_story_style: DimensionBreakdown[];
}
