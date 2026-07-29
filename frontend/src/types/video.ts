export type Platform = "youtube" | "tiktok" | "facebook" | "instagram" | "unknown";

export type ContentType = "video" | "playlist" | "channel";

export interface VideoInfo {
  id: string;
  title: string;
  thumbnailUrl: string;
  author: string;
  views: number;
  uploadDate: string;
  durationSec: number;
}

export interface SingleVideoResult {
  contentType: "video";
  platform: Platform;
  video: VideoInfo;
}

export interface CollectionResult {
  contentType: "playlist" | "channel";
  platform: Platform;
  title: string;
  author: string;
  videos: VideoInfo[];
}

export type AnalyzeResult = SingleVideoResult | CollectionResult;
