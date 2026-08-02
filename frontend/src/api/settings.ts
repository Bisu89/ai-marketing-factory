import { apiGet, apiPut } from "./client";
import type { AppSettings, BrowseFoldersResult } from "../types/settings";

export async function getSettings(): Promise<AppSettings> {
  return apiGet<AppSettings>("/settings");
}

export async function updateLibraryDir(path: string): Promise<{ library_dir: string }> {
  return apiPut<{ library_dir: string }>("/settings/library-dir", { path });
}

export async function browseFolders(path?: string): Promise<BrowseFoldersResult> {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return apiGet<BrowseFoldersResult>(`/settings/browse-folders${query}`);
}
