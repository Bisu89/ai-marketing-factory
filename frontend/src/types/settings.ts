export interface AppSettings {
  library_dir: string;
  download_dir: string;
  max_concurrent_downloads: number;
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
