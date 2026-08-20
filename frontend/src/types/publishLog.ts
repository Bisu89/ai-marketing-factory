export type PublishLogStatus = "none" | "winner" | "loser" | "archived";

export const PUBLISH_LOG_STATUS_LABELS: Record<PublishLogStatus, string> = {
  none: "Chưa đánh giá",
  winner: "Winner",
  loser: "Loser",
  archived: "Đã lưu trữ",
};

// Kept here (not re-fetched from an AI Story module -- that generator was
// removed, see docs/features/63-remove-ai-content-and-insights.md) purely
// as manual labels for the free-text `story_style` field below.
export type StoryStyle =
  | "emotional"
  | "humorous"
  | "inspirational"
  | "dramatic"
  | "educational"
  | "sales";

export const STORY_STYLE_LABELS: Record<StoryStyle, string> = {
  emotional: "Cảm động",
  humorous: "Hài hước",
  inspirational: "Truyền cảm hứng",
  dramatic: "Kịch tính",
  educational: "Giáo dục",
  sales: "Bán hàng",
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
  notes: string | null;
  created_at: string;
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
