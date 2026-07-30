import type { MouseEvent } from "react";
import { Star, FolderOpen, Copy, Eye, HardDrive } from "lucide-react";
import { mediaUrl } from "../../../api/client";
import { PlatformBadge } from "../../../components/PlatformBadge";
import type { Platform } from "../../../types/video";
import { formatDuration } from "../../../utils/format";
import type { VideoOut } from "../types";
import { formatFileSize, formatShortDate } from "../utils";
import { StatusBadge } from "./StatusBadge";
import "./VideoCard.css";

interface VideoCardProps {
  video: VideoOut;
  categoryName?: string;
  onToggleFavorite: () => void;
  onOpenFolder: () => void;
  onPreview: () => void;
}

export function VideoCard({ video, categoryName, onToggleFavorite, onOpenFolder, onPreview }: VideoCardProps) {
  function copyUrl(e: MouseEvent) {
    e.stopPropagation();
    navigator.clipboard.writeText(video.original_url);
  }

  function toggleFavorite(e: MouseEvent) {
    e.stopPropagation();
    onToggleFavorite();
  }

  function openFolder(e: MouseEvent) {
    e.stopPropagation();
    onOpenFolder();
  }

  return (
    <div className="video-card" onClick={onPreview}>
      <div className="video-card-thumb-wrap">
        {video.thumbnail_media_url ? (
          <img src={mediaUrl(video.thumbnail_media_url)} alt="" className="video-card-thumb" />
        ) : (
          <div className="video-card-thumb video-card-thumb-placeholder">
            <HardDrive size={22} />
          </div>
        )}
        <button
          className={`video-card-favorite${video.is_favorite ? " is-favorite" : ""}`}
          onClick={toggleFavorite}
          aria-label="Favorite"
        >
          <Star size={15} fill={video.is_favorite ? "currentColor" : "none"} />
        </button>
        {video.duration_sec != null && (
          <span className="video-card-duration">{formatDuration(video.duration_sec)}</span>
        )}
      </div>

      <div className="video-card-body">
        <div className="video-card-top-row">
          <PlatformBadge platform={video.platform as Platform} />
          <StatusBadge status={video.status} />
        </div>

        <h3 className="video-card-title" title={video.title}>
          {video.title}
        </h3>
        <p className="video-card-channel">{video.channel_name}</p>

        <div className="video-card-meta">
          <span>{video.resolution ?? "—"}</span>
          <span>{formatFileSize(video.filesize_bytes)}</span>
          <span>{formatShortDate(video.downloaded_at)}</span>
        </div>

        {(categoryName || video.tags.length > 0) && (
          <div className="video-card-tags">
            {categoryName && <span className="video-card-category">{categoryName}</span>}
            {video.tags.map((tag) => (
              <span key={tag} className="video-card-tag">
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="video-card-actions">
        <button onClick={openFolder} title="Open Folder" aria-label="Open Folder">
          <FolderOpen size={15} />
        </button>
        <button onClick={copyUrl} title="Copy URL" aria-label="Copy URL">
          <Copy size={15} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPreview();
          }}
          title="Preview"
          aria-label="Preview"
        >
          <Eye size={15} />
        </button>
      </div>
    </div>
  );
}
