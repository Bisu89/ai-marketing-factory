import { Download, User, Eye, Calendar, Clock } from "lucide-react";
import type { Platform, VideoInfo } from "../types/video";
import { formatDuration, formatViews } from "../utils/format";
import { PlatformBadge } from "./PlatformBadge";
import "./VideoResultCard.css";

interface VideoResultCardProps {
  platform: Platform;
  video: VideoInfo;
  onDownload: () => void;
}

export function VideoResultCard({ platform, video, onDownload }: VideoResultCardProps) {
  return (
    <div className="result-card">
      <img className="result-card-thumb" src={video.thumbnailUrl} alt="" />
      <div className="result-card-body">
        <PlatformBadge platform={platform} />
        <h3 className="result-card-title">{video.title}</h3>
        <div className="result-card-meta">
          <span>
            <User size={14} /> {video.author}
          </span>
          <span>
            <Eye size={14} /> {formatViews(video.views)} views
          </span>
          <span>
            <Calendar size={14} /> {video.uploadDate}
          </span>
          <span>
            <Clock size={14} /> {formatDuration(video.durationSec)}
          </span>
        </div>
      </div>
      <button className="btn btn-primary result-card-download" onClick={onDownload}>
        <Download size={16} />
        Tải xuống
      </button>
    </div>
  );
}
