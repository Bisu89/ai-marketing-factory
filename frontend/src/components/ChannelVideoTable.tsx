import { useMemo, useState } from "react";
import { Download, DownloadCloud } from "lucide-react";
import type { Platform, VideoInfo } from "../types/video";
import { formatDuration, formatViews } from "../utils/format";
import { PlatformBadge } from "./PlatformBadge";
import "./ChannelVideoTable.css";

interface ChannelVideoTableProps {
  platform: Platform;
  contentType: "playlist" | "channel";
  title: string;
  author: string;
  videos: VideoInfo[];
  onDownloadAll: (limit: number) => void;
  onDownloadSelected: (videoIds: string[]) => void;
}

export function ChannelVideoTable({
  platform,
  contentType,
  title,
  author,
  videos,
  onDownloadAll,
  onDownloadSelected,
}: ChannelVideoTableProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState(videos.length);

  const allSelected = selectedIds.size === videos.length && videos.length > 0;

  const clampedLimit = useMemo(
    () => Math.min(Math.max(1, limit || 1), videos.length),
    [limit, videos.length],
  );

  function toggleOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds(allSelected ? new Set() : new Set(videos.map((v) => v.id)));
  }

  return (
    <div className="channel-table-wrap">
      <div className="channel-table-header">
        <div>
          <div className="channel-table-title-row">
            <PlatformBadge platform={platform} />
            <span className="channel-table-type">{contentType === "channel" ? "Channel" : "Playlist"}</span>
          </div>
          <h3 className="channel-table-title">{title}</h3>
          <p className="channel-table-author">{author}</p>
        </div>

        <div className="channel-table-actions">
          <label className="channel-table-limit">
            Giới hạn số video
            <input
              type="number"
              min={1}
              max={videos.length}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
            <span>/ {videos.length}</span>
          </label>

          <button
            className="btn btn-secondary"
            disabled={selectedIds.size === 0}
            onClick={() => onDownloadSelected(Array.from(selectedIds))}
          >
            <Download size={16} />
            Download Selected ({selectedIds.size})
          </button>

          <button className="btn btn-primary" onClick={() => onDownloadAll(clampedLimit)}>
            <DownloadCloud size={16} />
            Download All ({clampedLimit})
          </button>
        </div>
      </div>

      <div className="channel-table-scroll">
        <table className="channel-table">
          <thead>
            <tr>
              <th className="channel-table-checkbox-col">
                <input type="checkbox" checked={allSelected} onChange={toggleAll} />
              </th>
              <th>Video</th>
              <th>Thời lượng</th>
              <th>Ngày đăng</th>
              <th>Lượt xem</th>
            </tr>
          </thead>
          <tbody>
            {videos.map((video) => (
              <tr key={video.id} className={selectedIds.has(video.id) ? "is-selected" : ""}>
                <td className="channel-table-checkbox-col">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(video.id)}
                    onChange={() => toggleOne(video.id)}
                  />
                </td>
                <td>
                  <div className="channel-table-video-cell">
                    <img src={video.thumbnailUrl} alt="" />
                    <span>{video.title}</span>
                  </div>
                </td>
                <td>{formatDuration(video.durationSec)}</td>
                <td>{video.uploadDate}</td>
                <td>{formatViews(video.views)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
