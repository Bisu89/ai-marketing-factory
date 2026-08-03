import type { VideoOut } from "../types";
import { VideoCard } from "./VideoCard";
import "./VideoGrid.css";

interface VideoGridProps {
  videos: VideoOut[];
  onToggleFavorite: (videoId: number, favorite: boolean) => void;
  onOpenFolder: (videoId: number) => void;
  onPreview: (videoId: number) => void;
}

export function VideoGrid({ videos, onToggleFavorite, onOpenFolder, onPreview }: VideoGridProps) {
  return (
    <div className="video-grid">
      {videos.map((video) => (
        <VideoCard
          key={video.id}
          video={video}
          onToggleFavorite={() => onToggleFavorite(video.id, !video.is_favorite)}
          onOpenFolder={() => onOpenFolder(video.id)}
          onPreview={() => onPreview(video.id)}
        />
      ))}
    </div>
  );
}
