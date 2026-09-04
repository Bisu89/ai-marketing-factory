export type AIProvider = "anthropic" | "openai";

export interface AppSettings {
  library_dir: string;
  download_dir: string;
  max_concurrent_downloads: number;
  ai_provider: AIProvider;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
  // Whether the *currently selected* provider (ai_provider) has a key
  // configured -- what most UI checks should read instead of assuming
  // Anthropic specifically.
  has_ai_key: boolean;
  // Competitor Content Analyzer (Task 11) -- TikTok Developer app
  // credentials, same "never echo the secret" shape as the AI keys above.
  has_tiktok_client_key: boolean;
  has_tiktok_client_secret: boolean;
  tiktok_redirect_uri: string | null;
  // YouTube Publishing — Google Cloud OAuth client (never echoed).
  has_google_oauth_client: boolean;
  youtube_redirect_uri: string;
  // Auto-delete a finished project's regenerable voice/motion/audio render
  // cache this many days after its render completes. 0 = off.
  render_cache_retention_days: number;
  // How often the News page re-fetches every enabled RSS source, in
  // minutes. 0 = off (feeds only pulled on a manual "Fetch").
  news_poll_interval_minutes: number;
}

export interface FolderEntry {
  name: string;
  path: string;
}

export interface BrowseFoldersResult {
  current_path: string | null;
  parent_path: string | null;
  folders: FolderEntry[];
}
