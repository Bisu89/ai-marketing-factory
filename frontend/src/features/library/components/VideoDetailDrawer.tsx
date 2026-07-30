import { Copy, FolderOpen, Star, X } from "lucide-react";
import { mediaUrl } from "../../../api/client";
import { PlatformBadge } from "../../../components/PlatformBadge";
import type { Platform } from "../../../types/video";
import { formatDuration } from "../../../utils/format";
import type { CategoryOut, VideoOut } from "../types";
import { formatFileSize, formatShortDate } from "../utils";
import { StatusBadge } from "./StatusBadge";
import "./VideoDetailDrawer.css";

interface VideoDetailDrawerProps {
  video: VideoOut;
  categories: CategoryOut[];
  onClose: () => void;
  onToggleFavorite: () => void;
  onOpenFolder: () => void;
}

export function VideoDetailDrawer({ video, categories, onClose, onToggleFavorite, onOpenFolder }: VideoDetailDrawerProps) {
  const categoryName = categories.find((c) => c.id === video.category_id)?.name;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="drawer-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="drawer-player">
          {video.video_media_url ? (
            <video controls src={mediaUrl(video.video_media_url)} poster={video.thumbnail_media_url ? mediaUrl(video.thumbnail_media_url) : undefined} />
          ) : video.thumbnail_media_url ? (
            <img src={mediaUrl(video.thumbnail_media_url)} alt="" />
          ) : (
            <div className="drawer-player-placeholder">Không có file để xem trước</div>
          )}
        </div>

        <div className="drawer-body">
          <div className="drawer-top-row">
            <PlatformBadge platform={video.platform as Platform} />
            <StatusBadge status={video.status} />
            <button
              className={`drawer-favorite${video.is_favorite ? " is-favorite" : ""}`}
              onClick={onToggleFavorite}
              aria-label="Favorite"
            >
              <Star size={16} fill={video.is_favorite ? "currentColor" : "none"} />
            </button>
          </div>

          <h2 className="drawer-title">{video.title}</h2>
          <p className="drawer-channel">{video.channel_name}</p>

          <dl className="drawer-meta-grid">
            <dt>Resolution</dt>
            <dd>{video.resolution ?? "—"}</dd>
            <dt>Duration</dt>
            <dd>{video.duration_sec != null ? formatDuration(video.duration_sec) : "—"}</dd>
            <dt>File size</dt>
            <dd>{formatFileSize(video.filesize_bytes)}</dd>
            <dt>Downloaded</dt>
            <dd>{formatShortDate(video.downloaded_at)}</dd>
            <dt>Category</dt>
            <dd>{categoryName ?? "—"}</dd>
          </dl>

          {video.tags.length > 0 && (
            <div className="drawer-tags">
              {video.tags.map((tag) => (
                <span key={tag} className="drawer-tag">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          <div className="drawer-row">
            <span className="drawer-row-label">Original URL</span>
            <div className="drawer-row-value">
              <span className="drawer-url" title={video.original_url}>
                {video.original_url}
              </span>
              <button onClick={() => navigator.clipboard.writeText(video.original_url)} title="Copy URL">
                <Copy size={14} />
              </button>
            </div>
          </div>

          <div className="drawer-row">
            <span className="drawer-row-label">Folder Path</span>
            <div className="drawer-row-value">
              <span className="drawer-url" title={video.video_path ?? ""}>
                {video.video_path ?? "—"}
              </span>
              <button onClick={onOpenFolder} title="Open Folder">
                <FolderOpen size={14} />
              </button>
            </div>
          </div>

          {video.notes && (
            <div className="drawer-notes">
              <span className="drawer-row-label">Notes</span>
              <p>{video.notes}</p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
