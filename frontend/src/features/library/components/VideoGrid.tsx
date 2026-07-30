import type { CategoryOut, VideoOut } from "../types";
import { VideoCard } from "./VideoCard";
import "./VideoGrid.css";

interface VideoGridProps {
  videos: VideoOut[];
  categories: CategoryOut[];
  onToggleFavorite: (videoId: number, favorite: boolean) => void;
  onOpenFolder: (videoId: number) => void;
  onPreview: (videoId: number) => void;
}

export function VideoGrid({ videos, categories, onToggleFavorite, onOpenFolder, onPreview }: VideoGridProps) {
  const categoryNameById = new Map(categories.map((c) => [c.id, c.name]));

  return (
    <div className="video-grid">
      {videos.map((video) => (
        <VideoCard
          key={video.id}
          video={video}
          categoryName={video.category_id != null ? categoryNameById.get(video.category_id) : undefined}
          onToggleFavorite={() => onToggleFavorite(video.id, !video.is_favorite)}
          onOpenFolder={() => onOpenFolder(video.id)}
          onPreview={() => onPreview(video.id)}
        />
      ))}
    </div>
  );
}
