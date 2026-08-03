import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, Search, Sparkles, Trash2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { fetchVideo, fetchVideos } from "../api/videos";
import { deleteStoryJob, generateStory, listStoryJobs, selectStoryVersion } from "../api/story";
import { getSettings } from "../api/settings";
import { mediaUrl } from "../api/client";
import type { VideoOut } from "../features/library/types";
import { STORY_STYLE_LABELS, type StoryJob, type StoryStyle } from "../types/story";
import "./StoryPage.css";

const STYLES = Object.keys(STORY_STYLE_LABELS) as StoryStyle[];

export function StoryPage() {
  const [searchParams] = useSearchParams();
  const preselectVideoId = searchParams.get("video_id");

  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);

  const [videoQuery, setVideoQuery] = useState("");
  const [videoResults, setVideoResults] = useState<VideoOut[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoOut | null>(null);
  const [style, setStyle] = useState<StoryStyle>("emotional");

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [latestJob, setLatestJob] = useState<StoryJob | null>(null);

  const [history, setHistory] = useState<StoryJob[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then((settings) => setHasApiKey(settings.has_anthropic_key))
      .catch(() => setHasApiKey(false));
  }, []);

  // Deep-link support: ?video_id=123 pre-selects a video (e.g. for a future
  // "Generate Story" button from the Library drawer), same URL-param
  // convention already used across this app (Library filters, view/page).
  useEffect(() => {
    if (!preselectVideoId) return;
    fetchVideo(Number(preselectVideoId))
      .then((video) => setSelectedVideo(video))
      .catch(() => {
        // Video may have been deleted since the link was created; ignore and
        // let the user pick one manually.
      });
  }, [preselectVideoId]);

  useEffect(() => {
    if (!videoQuery.trim()) {
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
  }, [videoQuery]);

  function loadHistory(videoId: number | undefined) {
    listStoryJobs(videoId)
      .then((jobs) => {
        setHistory(jobs);
        setHistoryError(null);
      })
      .catch(() => setHistoryError("Không tải được lịch sử tạo story."));
  }

  useEffect(() => {
    loadHistory(selectedVideo?.id);
  }, [selectedVideo?.id]);

  async function handleGenerate() {
    if (!selectedVideo || generating) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const job = await generateStory({ video_id: selectedVideo.id, style });
      setLatestJob(job);
      loadHistory(selectedVideo.id);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Không tạo được story.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectVersion(job: StoryJob, versionId: number) {
    try {
      const updated = await selectStoryVersion(job.id, versionId);
      if (latestJob?.id === job.id) setLatestJob(updated);
      setHistory((prev) => prev.map((j) => (j.id === job.id ? updated : j)));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  async function handleDeleteJob(jobId: number) {
    try {
      await deleteStoryJob(jobId);
      if (latestJob?.id === jobId) setLatestJob(null);
      setHistory((prev) => prev.filter((j) => j.id !== jobId));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  return (
    <>
      <PageHeader
        title="AI Story"
        subtitle="Tạo kịch bản lời dẫn tiếng Tây Ban Nha cho video từ metadata (chủ đề, cảm xúc, tag, ghi chú)"
      />

      {hasApiKey === false && (
        <div className="story-alert story-alert-warning">
          <AlertTriangle size={16} />
          Chưa cấu hình Anthropic API key. Vào <Link to="/settings">Settings</Link> để nhập key trước khi tạo story.
        </div>
      )}

      <div className="story-form">
        <div className="story-video-picker">
          <div className="story-search-row">
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
            <ul className="story-video-results">
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

        {selectedVideo && (
          <div className="story-video-meta">
            <span>Chủ đề: {selectedVideo.category ?? "—"}</span>
            <span>Cảm xúc: {selectedVideo.emotion ?? "—"}</span>
            <span>Tag: {selectedVideo.tags.map((t) => t.name).join(", ") || "—"}</span>
          </div>
        )}

        <label className="story-style-select">
          Phong cách kể chuyện
          <select value={style} onChange={(e) => setStyle(e.target.value as StoryStyle)}>
            {STYLES.map((s) => (
              <option key={s} value={s}>
                {STORY_STYLE_LABELS[s]}
              </option>
            ))}
          </select>
        </label>

        {generateError && <div className="story-alert story-alert-error">{generateError}</div>}

        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={!selectedVideo || generating || hasApiKey === false}
        >
          {generating ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
          Tạo Story
        </button>
      </div>

      {latestJob && (
        <>
          <h2 className="story-section-title">Kết quả vừa tạo</h2>
          <StoryJobCard job={latestJob} onSelectVersion={handleSelectVersion} onDelete={handleDeleteJob} />
        </>
      )}

      <h2 className="story-section-title">Lịch sử {selectedVideo ? "của video này" : "tất cả"}</h2>

      {historyError && <div className="story-alert story-alert-error">{historyError}</div>}

      {history.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="Chưa có story nào"
          description="Chọn video và bấm 'Tạo Story' để bắt đầu."
        />
      ) : (
        <div className="story-jobs">
          {history
            .filter((job) => job.id !== latestJob?.id)
            .map((job) => (
              <StoryJobCard key={job.id} job={job} onSelectVersion={handleSelectVersion} onDelete={handleDeleteJob} />
            ))}
        </div>
      )}
    </>
  );
}

function StoryJobCard({
  job,
  onSelectVersion,
  onDelete,
}: {
  job: StoryJob;
  onSelectVersion: (job: StoryJob, versionId: number) => void;
  onDelete: (jobId: number) => void;
}) {
  return (
    <div className="story-job-card">
      <div className="story-job-header">
        <div>
          <span className="story-job-style">{STORY_STYLE_LABELS[job.style]}</span>
          <span className="story-job-date">{new Date(job.created_at).toLocaleString("vi-VN")}</span>
        </div>
        <button className="btn btn-secondary story-job-delete" onClick={() => onDelete(job.id)}>
          <Trash2 size={14} />
        </button>
      </div>

      {job.status === "failed" && job.error_message && (
        <div className="story-alert story-alert-error">{job.error_message}</div>
      )}

      {job.status === "completed" && (
        <div className="story-versions">
          {job.versions.map((version) => (
            <div key={version.id} className={`story-version${version.is_selected ? " story-version--selected" : ""}`}>
              <div className="story-version-title">{version.title}</div>
              <p className="story-version-text">{version.script_text}</p>
              <button
                className="btn btn-secondary"
                onClick={() => onSelectVersion(job, version.id)}
                disabled={version.is_selected}
              >
                {version.is_selected ? <CheckCircle2 size={14} /> : null}
                {version.is_selected ? "Đã chọn" : "Chọn phiên bản này"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
