import type { AnalyzeResult, Platform, VideoInfo } from "../types/video";
import { placeholderThumbnail } from "./placeholderThumbnail";

function detectPlatform(url: string): Platform {
  if (/youtube\.com|youtu\.be/i.test(url)) return "youtube";
  if (/tiktok\.com/i.test(url)) return "tiktok";
  if (/facebook\.com|fb\.watch/i.test(url)) return "facebook";
  if (/instagram\.com/i.test(url)) return "instagram";
  return "unknown";
}

function detectContentType(url: string): "video" | "playlist" | "channel" {
  if (/\/channel\/|\/@|\/c\//i.test(url)) return "channel";
  if (/[?&]list=|\/playlist/i.test(url)) return "playlist";
  return "video";
}

function buildMockVideo(index: number): VideoInfo {
  return {
    id: `mock-video-${index}`,
    title: `Video mẫu #${index + 1}`,
    thumbnailUrl: placeholderThumbnail(index),
    author: "Kênh Demo",
    views: Math.floor(1_000 + Math.random() * 500_000),
    uploadDate: new Date(Date.now() - index * 86_400_000).toISOString().slice(0, 10),
    durationSec: 60 + Math.floor(Math.random() * 900),
  };
}

// Mock cho Sprint 2 (UI-only). Backend chưa có endpoint detect/download thật —
// hàm này sẽ được thay bằng gọi API khi DetectionService phía backend sẵn sàng.
export async function analyzeUrl(url: string): Promise<AnalyzeResult> {
  await new Promise((resolve) => setTimeout(resolve, 700));

  const platform = detectPlatform(url);
  const contentType = detectContentType(url);

  if (contentType === "video") {
    return {
      contentType: "video",
      platform,
      video: buildMockVideo(0),
    };
  }

  const count = contentType === "channel" ? 24 : 12;
  return {
    contentType,
    platform,
    title: contentType === "channel" ? "Kênh Demo" : "Playlist Demo",
    author: "Kênh Demo",
    videos: Array.from({ length: count }, (_, i) => buildMockVideo(i)),
  };
}
