import { apiPost } from "./client";
import { placeholderThumbnail } from "../mock/placeholderThumbnail";
import type { AnalyzeResult, VideoInfo } from "../types/video";

function seedFromId(id: string): number {
  let sum = 0;
  for (let i = 0; i < id.length; i++) sum += id.charCodeAt(i);
  return sum;
}

function withThumbnailFallback(video: VideoInfo): VideoInfo {
  if (video.thumbnailUrl) return video;
  return { ...video, thumbnailUrl: placeholderThumbnail(seedFromId(video.id)) };
}

export async function detectUrl(url: string): Promise<AnalyzeResult> {
  const result = await apiPost<AnalyzeResult>("/detect", { url });

  if (result.contentType === "video") {
    return { ...result, video: withThumbnailFallback(result.video) };
  }
  return { ...result, videos: result.videos.map(withThumbnailFallback) };
}
