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
