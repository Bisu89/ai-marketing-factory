import { apiGet, apiPost } from "./client";

export interface ManhuaFetchChapter {
  n: number | null;
  saved: number;
  skipped: number;
}

export interface ManhuaFetchResult {
  id: number;
  chapter_dir: string;
  total_saved: number;
  total_skipped: number;
  chapters: ManhuaFetchChapter[];
}

export interface ManhuaFetchLogEntry {
  id: number;
  url: string;
  chapter_dir: string;
  count: number;
  saved: number;
  skipped: number;
  error: string | null;
  created_at: string;
}

export async function fetchManhuaChapter(
  url: string,
  chapterDir: string,
  count: number,
): Promise<ManhuaFetchResult> {
  return apiPost<ManhuaFetchResult>("/manhua-recap/fetch", {
    url,
    chapter_dir: chapterDir,
    count,
  });
}

export async function getManhuaFetchLog(): Promise<ManhuaFetchLogEntry[]> {
  return apiGet<ManhuaFetchLogEntry[]>("/manhua-recap/fetch-log");
}
