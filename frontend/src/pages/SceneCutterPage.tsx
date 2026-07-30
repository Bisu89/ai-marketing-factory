import { useEffect, useState } from "react";
import { Scissors, Search, Loader2, FolderOpen } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { fetchVideos } from "../api/videos";
import { createSceneJob, listSceneJobs } from "../api/sceneCutter";
import { mediaUrl } from "../api/client";
import type { VideoOut } from "../features/library/types";
import type { SceneCutJob } from "../types/sceneCutter";
import "./SceneCutterPage.css";

const POLL_INTERVAL_MS = 2000;

type SourceMode = "library" | "path";

const STATUS_LABEL: Record<SceneCutJob["status"], string> = {
  queued: "Trong hàng đợi",
  analyzing: "Đang phân tích cảnh",
  splitting: "Đang cắt video",
  completed: "Hoàn tất",
  failed: "Lỗi",
};

export function SceneCutterPage() {
  const [sourceMode, setSourceMode] = useState<SourceMode>("library");

  const [videoQuery, setVideoQuery] = useState("");
  const [videoResults, setVideoResults] = useState<VideoOut[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoOut | null>(null);

  const [sourcePath, setSourcePath] = useState("");

  const [threshold, setThreshold] = useState(46);
  const [minSceneLen, setMinSceneLen] = useState(0.6);
  const [trim, setTrim] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [jobs, setJobs] = useState<SceneCutJob[]>([]);

  // Live search against the Library while the user types a video title --
  // debounced so we don't fire a request per keystroke.
  useEffect(() => {
    if (sourceMode !== "library" || !videoQuery.trim()) {
      setVideoResults([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const data = await fetchVideos({ page: 1, page_size: 6, sort: "newest", search: videoQuery.trim() });
        if (!cancelled) setVideoResults(data.items);
      } catch {
        // Bỏ qua lỗi tìm kiếm tạm thời, thử lại khi người dùng gõ tiếp.
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [videoQuery, sourceMode]);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await listSceneJobs();
        if (!cancelled) setJobs(data);
      } catch {
        // Bỏ qua lỗi mạng tạm thời của một lượt poll, thử lại ở lượt sau.
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const canSubmit = sourceMode === "library" ? selectedVideo != null : sourcePath.trim().length > 0;

  async function handleSubmit() {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createSceneJob({
        video_id: sourceMode === "library" ? selectedVideo!.id : undefined,
        source_path: sourceMode === "path" ? sourcePath.trim() : undefined,
        threshold,
        min_scene_len_sec: minSceneLen,
        trim_sec: trim,
      });
      const data = await listSceneJobs();
      setJobs(data);
      setSelectedVideo(null);
      setVideoQuery("");
      setSourcePath("");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Không tạo được tác vụ cắt cảnh.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Scene Cutter"
        subtitle="Tự động phát hiện chuyển cảnh và cắt video thành từng cảnh riêng biệt"
      />

      <div className="scene-cutter-form">
        <div className="scene-cutter-source-tabs">
          <button
            className={`scene-cutter-tab${sourceMode === "library" ? " active" : ""}`}
            onClick={() => setSourceMode("library")}
          >
            Chọn từ Library
          </button>
          <button
            className={`scene-cutter-tab${sourceMode === "path" ? " active" : ""}`}
            onClick={() => setSourceMode("path")}
          >
            Đường dẫn file cục bộ
          </button>
        </div>

        {sourceMode === "library" ? (
          <div className="scene-cutter-video-picker">
            <div className="scene-cutter-search-row">
              <Search size={15} />
              <input
                type="text"
                placeholder="Tìm video trong Library theo tên..."
                value={selectedVideo ? selectedVideo.title : videoQuery}
                onChange={(e) => {
                  setSelectedVideo(null);
                  setVideoQuery(e.target.value);
                }}
              />
            </div>
            {videoResults.length > 0 && !selectedVideo && (
              <ul className="scene-cutter-video-results">
                {videoResults.map((video) => (
                  <li key={video.id}>
                    <button
                      onClick={() => {
                        setSelectedVideo(video);
                        setVideoResults([]);
                      }}
                    >
                      {video.thumbnail_media_url && <img src={mediaUrl(video.thumbnail_media_url)} alt="" />}
                      <span>{video.title}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <input
            className="scene-cutter-path-input"
            type="text"
            placeholder="VD: C:\Videos\clip.mp4"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
          />
        )}

        <div className="scene-cutter-params">
          <label>
            Độ nhạy (threshold)
            <input
              type="number"
              value={threshold}
              step={1}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
          </label>
          <label>
            Cảnh tối thiểu (giây)
            <input
              type="number"
              value={minSceneLen}
              step={0.1}
              onChange={(e) => setMinSceneLen(Number(e.target.value))}
            />
          </label>
          <label>
            Trim đầu/cuối (giây)
            <input type="number" value={trim} step={0.05} onChange={(e) => setTrim(Number(e.target.value))} />
          </label>
        </div>

        {submitError && <div className="scene-cutter-alert scene-cutter-alert-error">{submitError}</div>}

        <button className="btn btn-primary" onClick={handleSubmit} disabled={!canSubmit || submitting}>
          {submitting ? <Loader2 size={16} className="spin" /> : <Scissors size={16} />}
          Cắt thành cảnh
        </button>
      </div>

      <h2 className="scene-cutter-jobs-title">Các tác vụ đã chạy</h2>

      {jobs.length === 0 ? (
        <EmptyState
          icon={Scissors}
          title="Chưa có tác vụ nào"
          description="Chọn video và bấm 'Cắt thành cảnh' để bắt đầu."
        />
      ) : (
        <div className="scene-cutter-jobs">
          {jobs.map((job) => (
            <SceneJobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </>
  );
}

function SceneJobCard({ job }: { job: SceneCutJob }) {
  const label = STATUS_LABEL[job.status];
  const source = job.video_id != null ? `Video #${job.video_id}` : job.source_path;

  return (
    <div className="scene-job-card">
      <div className="scene-job-header">
        <div>
          <div className="scene-job-source">{source}</div>
          <div className={`scene-job-status scene-job-status--${job.status}`}>
            {(job.status === "analyzing" || job.status === "splitting" || job.status === "queued") && (
              <Loader2 size={13} className="spin" />
            )}
            {label}
            {job.scene_count != null && ` — ${job.scene_count} cảnh`}
          </div>
        </div>
      </div>

      {job.status === "failed" && job.error_message && (
        <div className="scene-cutter-alert scene-cutter-alert-error">{job.error_message}</div>
      )}

      {job.status === "completed" && job.scenes.length > 0 && (
        <div className="scene-job-scenes">
          {job.scenes.map((scene) => (
            <div key={scene.scene_number} className="scene-job-scene">
              {scene.media_url ? (
                <video src={mediaUrl(scene.media_url)} controls preload="metadata" />
              ) : (
                <div className="scene-job-scene-nopreview">
                  <FolderOpen size={20} />
                </div>
              )}
              <div className="scene-job-scene-label">
                Cảnh {scene.scene_number}: {scene.start_timecode} → {scene.end_timecode}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
