export type ViewMode = "grid" | "table";

export interface VideoTagOut {
  id: number;
  name: string;
}

export interface VideoOut {
  id: number;
  platform: string;
  external_id: string;
  channel_id: number;
  channel_name: string;
  title: string;
  original_url: string;
  thumbnail_url: string | null;
  thumbnail_path: string | null;
  video_path: string | null;
  thumbnail_media_url: string | null;
  video_media_url: string | null;
  views: number | null;
  likes: number | null;
  duration_sec: number | null;
  upload_date: string | null;
  status: string;
  category_id: number | null;
  category: string | null;
  emotion_id: number | null;
  emotion: string | null;
  notes: string | null;
  resolution: string | null;
  filesize_bytes: number | null;
  file_hash: string | null;
  is_favorite: boolean;
  tags: VideoTagOut[];
  is_downloaded: boolean;
  downloaded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoListResponse {
  items: VideoOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface VideoListParams {
  page: number;
  page_size: number;
  sort: string;
  search?: string;
  platform?: string;
  status?: string;
  category_id?: number;
  emotion_id?: number;
  tag?: string;
  favorite?: boolean;
  duration?: string;
  resolution?: string;
}

export interface CategoryOut {
  id: number;
  name: string;
  created_at: string;
}

export interface EmotionOut {
  id: number;
  name: string;
  created_at: string;
}
