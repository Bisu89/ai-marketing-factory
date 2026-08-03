import { useState } from "react";
import { Copy, FolderOpen, Plus, Star, X } from "lucide-react";
import { mediaUrl } from "../../../api/client";
import { PlatformBadge } from "../../../components/PlatformBadge";
import type { Platform } from "../../../types/video";
import { formatDuration } from "../../../utils/format";
import { STATUS_LABELS, STATUS_ORDER } from "./StatusBadge";
import type { CategoryOut, EmotionOut, VideoOut } from "../types";
import { formatFileSize, formatShortDate } from "../utils";
import "./VideoDetailDrawer.css";

interface VideoDetailDrawerProps {
  video: VideoOut;
  categories: CategoryOut[];
  emotions: EmotionOut[];
  onClose: () => void;
  onToggleFavorite: () => void;
  onOpenFolder: () => void;
  onUpdate: (patch: { status?: string; category_id?: number; emotion_id?: number; notes?: string }) => void;
  onAddTags: (tagNames: string[]) => void;
  onRemoveTag: (tagId: number) => void;
}

export function VideoDetailDrawer({
  video,
  categories,
  emotions,
  onClose,
  onToggleFavorite,
  onOpenFolder,
  onUpdate,
  onAddTags,
  onRemoveTag,
}: VideoDetailDrawerProps) {
  const [notesDraft, setNotesDraft] = useState(video.notes ?? "");
  const [notesVideoId, setNotesVideoId] = useState(video.id);
  const [newTag, setNewTag] = useState("");

  // The notes textarea needs local draft state to type into, but that draft
  // must reset whenever a *different* video is opened in the drawer --
  // tracking the id it was drafted for is simpler and more predictable than
  // a useEffect keyed on video.id.
  if (notesVideoId !== video.id) {
    setNotesVideoId(video.id);
    setNotesDraft(video.notes ?? "");
  }

  const notesDirty = notesDraft !== (video.notes ?? "");

  function handleAddTag() {
    const names = newTag
      .split(",")
      .map((n) => n.trim())
      .filter(Boolean);
    if (names.length === 0) return;
    onAddTags(names);
    setNewTag("");
  }

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
            <select
              className={`status-badge drawer-status-select status-badge--${video.status}`}
              value={video.status}
              onChange={(e) => onUpdate({ status: e.target.value })}
            >
              {STATUS_ORDER.map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status]}
                </option>
              ))}
            </select>
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
          </dl>

          <div className="drawer-field-row">
            <label className="drawer-field">
              Topic
              <select
                value={video.category_id ?? ""}
                onChange={(e) => onUpdate({ category_id: Number(e.target.value) })}
              >
                <option value="" disabled>
                  Chọn topic...
                </option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="drawer-field">
              Emotion
              <select
                value={video.emotion_id ?? ""}
                onChange={(e) => onUpdate({ emotion_id: Number(e.target.value) })}
              >
                <option value="" disabled>
                  Chọn emotion...
                </option>
                {emotions.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="drawer-tags-section">
            <span className="drawer-row-label">Tags</span>
            <div className="drawer-tags">
              {video.tags.map((tag) => (
                <span key={tag.id} className="drawer-tag">
                  #{tag.name}
                  <button onClick={() => onRemoveTag(tag.id)} aria-label={`Remove tag ${tag.name}`}>
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
            <div className="drawer-tag-add-row">
              <input
                type="text"
                placeholder="Thêm tag, cách nhau bằng dấu phẩy"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddTag()}
              />
              <button onClick={handleAddTag} aria-label="Add tag" disabled={!newTag.trim()}>
                <Plus size={14} />
              </button>
            </div>
          </div>

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

          <div className="drawer-notes">
            <span className="drawer-row-label">Notes</span>
            <textarea
              rows={4}
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              placeholder="Ghi chú cho video này..."
            />
            {notesDirty && (
              <button className="btn btn-primary drawer-notes-save" onClick={() => onUpdate({ notes: notesDraft })}>
                Lưu ghi chú
              </button>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
