// Mirrors backend/app/modules/competitor_intelligence/schemas.py exactly
// -- see docs/features/76-competitor-content-analyzer.md.

export interface TikTokAccount {
  id: number;
  open_id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  follower_count: number | null;
  following_count: number | null;
  likes_count: number | null;
  video_count: number | null;
  status: string;
  scope: string;
  connected_at: string;
  last_synced_at: string | null;
}

export interface TikTokVideo {
  id: number;
  tiktok_video_id: string;
  title: string | null;
  video_description: string | null;
  duration_sec: number | null;
  cover_image_url: string | null;
  share_url: string | null;
  view_count: number | null;
  like_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  posted_at: string | null;
  synced_at: string;
}

export interface CompetitorVideoCreate {
  source_url: string;
  competitor_handle?: string | null;
  title_caption?: string | null;
  duration_sec?: number | null;
  notes?: string | null;
}

export interface CompetitorVideo {
  id: number;
  source_url: string;
  competitor_handle: string | null;
  title_caption: string | null;
  thumbnail_url: string | null;
  author_name: string | null;
  duration_sec: number | null;
  notes: string | null;
  added_at: string;

  emotional_pattern: string | null;
  hook_structure: string | null;
  conflict_type: string | null;
  character_type: string | null;
  ending_style: string | null;
  estimated_format: string | null;
  reasoning: string | null;
  analyzed_at: string | null;
}
