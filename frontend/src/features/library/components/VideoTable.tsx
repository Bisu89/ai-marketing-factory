import { Copy, Eye, FolderOpen, HardDrive, Star } from "lucide-react";
import { mediaUrl } from "../../../api/client";
import { PlatformBadge } from "../../../components/PlatformBadge";
import type { Platform } from "../../../types/video";
import { formatDuration } from "../../../utils/format";
import type { VideoOut } from "../types";
import { formatFileSize, formatShortDate } from "../utils";
import { StatusBadge } from "./StatusBadge";
import "./VideoTable.css";

interface VideoTableProps {
  videos: VideoOut[];
  onToggleFavorite: (videoId: number, favorite: boolean) => void;
  onOpenFolder: (videoId: number) => void;
  onPreview: (videoId: number) => void;
}

export function VideoTable({ videos, onToggleFavorite, onOpenFolder, onPreview }: VideoTableProps) {
  return (
    <div className="video-table-wrap">
      <table className="video-table">
        <thead>
          <tr>
            <th className="video-table-fav-col" />
            <th>Video</th>
            <th>Platform</th>
            <th>Duration</th>
            <th>Resolution</th>
            <th>Size</th>
            <th>Downloaded</th>
            <th>Status</th>
            <th>Topic</th>
            <th>Emotion</th>
            <th>Tags</th>
            <th className="video-table-actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {videos.map((video) => (
            <tr key={video.id} onClick={() => onPreview(video.id)}>
              <td className="video-table-fav-col">
                <button
                  className={`video-table-favorite${video.is_favorite ? " is-favorite" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleFavorite(video.id, !video.is_favorite);
                  }}
                  aria-label="Favorite"
                >
                  <Star size={14} fill={video.is_favorite ? "currentColor" : "none"} />
                </button>
              </td>
              <td>
                <div className="video-table-video-cell">
                  {video.thumbnail_media_url ? (
                    <img src={mediaUrl(video.thumbnail_media_url)} alt="" />
                  ) : (
                    <div className="video-table-thumb-placeholder">
                      <HardDrive size={14} />
                    </div>
                  )}
                  <div>
                    <div className="video-table-title">{video.title}</div>
                    <div className="video-table-channel">{video.channel_name}</div>
                  </div>
                </div>
              </td>
              <td>
                <PlatformBadge platform={video.platform as Platform} />
              </td>
              <td>{video.duration_sec != null ? formatDuration(video.duration_sec) : "—"}</td>
              <td>{video.resolution ?? "—"}</td>
              <td>{formatFileSize(video.filesize_bytes)}</td>
              <td>{formatShortDate(video.downloaded_at)}</td>
              <td>
                <StatusBadge status={video.status} />
              </td>
              <td>{video.category ?? "—"}</td>
              <td>{video.emotion ?? "—"}</td>
              <td className="video-table-tags-cell">
                {video.tags.length > 0 ? video.tags.map((t) => `#${t.name}`).join(" ") : "—"}
              </td>
              <td className="video-table-actions-col">
                <div className="video-table-actions">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenFolder(video.id);
                    }}
                    title="Open Folder"
                    aria-label="Open Folder"
                  >
                    <FolderOpen size={14} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(video.original_url);
                    }}
                    title="Copy URL"
                    aria-label="Copy URL"
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onPreview(video.id);
                    }}
                    title="Preview"
                    aria-label="Preview"
                  >
                    <Eye size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
