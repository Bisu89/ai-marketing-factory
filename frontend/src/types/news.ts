export type NewsItemStatus = "new" | "drafted" | "queued" | "used" | "dismissed";

export interface NewsSource {
  id: number;
  name: string;
  feed_url: string;
  enabled: boolean;
  category: string | null;
  language: string;
  last_fetched_at: string | null;
  last_error: string | null;
  created_at: string | null;
  pending_items: number | null;
}

export interface NewsSourceCreateInput {
  name: string;
  feed_url: string;
  category?: string | null;
  language?: string;
  enabled?: boolean;
}

export interface NewsSourceUpdateInput {
  name?: string;
  feed_url?: string;
  category?: string | null;
  language?: string;
  enabled?: boolean;
}

export interface NewsItem {
  id: number;
  source_id: number;
  source_name: string | null;
  title: string;
  summary: string | null;
  link: string | null;
  image_url: string | null;
  published_at: string | null;
  status: NewsItemStatus;
  script_text: string | null;
  project_id: number | null;
  batch_id: number | null;
  created_at: string | null;
}

export interface NewsItemListResponse {
  items: NewsItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface FetchResult {
  source_id: number;
  source_name: string;
  fetched: number;
  new_items: number;
  duplicates: number;
  error: string | null;
}

export interface FetchAllResponse {
  results: FetchResult[];
  total_new_items: number;
}

export interface DraftScriptsResponse {
  drafted: number;
  failed: number;
  errors: string[];
}
