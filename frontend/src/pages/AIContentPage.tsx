import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Copy, Heart, Loader2, RefreshCw, Search, Sparkles, Trash2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { fetchVideo, fetchVideos } from "../api/videos";
import { deleteStoryJob, generateStory, listStoryJobs, selectStoryVersion } from "../api/story";
import { deleteHookJob, generateHooks, listHookJobs, toggleHookFavorite } from "../api/hook";
import { deleteCaptionJob, generateCaptions, listCaptionJobs, selectCaptionVersion } from "../api/caption";
import { getSettings } from "../api/settings";
import { mediaUrl } from "../api/client";
import type { VideoOut } from "../features/library/types";
import { STORY_LANGUAGE_LABELS, STORY_STYLE_LABELS, type StoryJob, type StoryLanguage, type StoryStyle } from "../types/story";
import type { HookJob } from "../types/hook";
import type { CaptionJob } from "../types/caption";
import "./AIContentPage.css";

const STYLES = Object.keys(STORY_STYLE_LABELS) as StoryStyle[];
const LANGUAGES = Object.keys(STORY_LANGUAGE_LABELS) as StoryLanguage[];
type Tab = "story" | "hook" | "caption";

export function AIContentPage() {
  const [searchParams] = useSearchParams();
  const preselectVideoId = searchParams.get("video_id");

  const [tab, setTab] = useState<Tab>("story");
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);

  const [videoQuery, setVideoQuery] = useState("");
  const [videoResults, setVideoResults] = useState<VideoOut[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoOut | null>(null);

  useEffect(() => {
    getSettings()
      .then((settings) => setHasApiKey(settings.has_anthropic_key))
      .catch(() => setHasApiKey(false));
  }, []);

  useEffect(() => {
    if (!preselectVideoId) return;
    fetchVideo(Number(preselectVideoId))
      .then((video) => setSelectedVideo(video))
      .catch(() => undefined);
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

  return (
    <>
      <PageHeader
        title="AI Content"
        subtitle="Tạo story, hook và caption cho video từ metadata (chủ đề, cảm xúc, tag, ghi chú)"
      />

      {hasApiKey === false && (
        <div className="ai-alert ai-alert-warning">
          <AlertTriangle size={16} />
          Chưa cấu hình Anthropic API key. Vào <Link to="/settings">Settings</Link> để nhập key trước khi tạo nội dung.
        </div>
      )}

      <div className="ai-video-picker">
        <div className="ai-search-row">
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
          <ul className="ai-video-results">
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
        <div className="ai-video-meta">
          <span>Chủ đề: {selectedVideo.category ?? "—"}</span>
          <span>Cảm xúc: {selectedVideo.emotion ?? "—"}</span>
          <span>Tag: {selectedVideo.tags.map((t) => t.name).join(", ") || "—"}</span>
        </div>
      )}

      <div className="ai-tabs">
        <button className={`btn ${tab === "story" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("story")}>
          Story
        </button>
        <button className={`btn ${tab === "hook" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("hook")}>
          Hook
        </button>
        <button className={`btn ${tab === "caption" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("caption")}>
          Caption
        </button>
      </div>

      {!selectedVideo ? (
        <EmptyState icon={Sparkles} title="Chưa chọn video" description="Tìm và chọn video ở trên để bắt đầu." />
      ) : tab === "story" ? (
        <StoryTab video={selectedVideo} disabled={hasApiKey === false} />
      ) : tab === "hook" ? (
        <HookTab video={selectedVideo} disabled={hasApiKey === false} />
      ) : (
        <CaptionTab video={selectedVideo} disabled={hasApiKey === false} />
      )}
    </>
  );
}

// ---------- Story tab ----------

function StoryTab({ video, disabled }: { video: VideoOut; disabled: boolean }) {
  const [style, setStyle] = useState<StoryStyle>("emotional");
  const [language, setLanguage] = useState<StoryLanguage>("english");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<StoryJob[]>([]);

  function load() {
    listStoryJobs(video.id).then(setJobs).catch(() => setError("Không tải được lịch sử story."));
  }

  useEffect(load, [video.id]);

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      await generateStory({ video_id: video.id, style, language });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được story.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectVersion(jobId: number, versionId: number) {
    try {
      const updated = await selectStoryVersion(jobId, versionId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  async function handleDelete(jobId: number) {
    try {
      await deleteStoryJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  return (
    <div className="ai-form">
      <label className="ai-style-select">
        Phong cách kể chuyện
        <select value={style} onChange={(e) => setStyle(e.target.value as StoryStyle)}>
          {STYLES.map((s) => (
            <option key={s} value={s}>
              {STORY_STYLE_LABELS[s]}
            </option>
          ))}
        </select>
      </label>

      <label className="ai-style-select">
        Ngôn ngữ kịch bản
        <select value={language} onChange={(e) => setLanguage(e.target.value as StoryLanguage)}>
          {LANGUAGES.map((l) => (
            <option key={l} value={l}>
              {STORY_LANGUAGE_LABELS[l]}
            </option>
          ))}
        </select>
      </label>

      {error && <div className="ai-alert ai-alert-error">{error}</div>}

      <button className="btn btn-primary" onClick={handleGenerate} disabled={disabled || generating}>
        {generating ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
        Tạo Story
      </button>

      {jobs.length === 0 ? (
        <EmptyState icon={Sparkles} title="Chưa có story nào" description="Bấm 'Tạo Story' để bắt đầu." />
      ) : (
        jobs.map((job) => (
          <div key={job.id} className="ai-job-card">
            <div className="ai-job-header">
              <span>
                {STORY_STYLE_LABELS[job.style]} · {STORY_LANGUAGE_LABELS[job.language]}
              </span>
              <span className="ai-job-date">{new Date(job.created_at).toLocaleString("vi-VN")}</span>
              <button className="ai-job-delete" onClick={() => handleDelete(job.id)}>
                <Trash2 size={13} />
              </button>
            </div>
            {job.status === "failed" && job.error_message && (
              <div className="ai-alert ai-alert-error">{job.error_message}</div>
            )}
            {job.status === "completed" && (
              <div className="ai-versions">
                {job.versions.map((v) => (
                  <div key={v.id} className={`ai-version${v.is_selected ? " ai-version--selected" : ""}`}>
                    <div className="ai-version-title">{v.title}</div>
                    <p className="ai-version-text">{v.script_text}</p>
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleSelectVersion(job.id, v.id)}
                      disabled={v.is_selected}
                    >
                      {v.is_selected ? <CheckCircle2 size={13} /> : null}
                      {v.is_selected ? "Đã chọn" : "Chọn phiên bản này"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ---------- Hook tab ----------

function HookTab({ video, disabled }: { video: VideoOut; disabled: boolean }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<HookJob[]>([]);

  function load() {
    listHookJobs(video.id).then(setJobs).catch(() => setError("Không tải được lịch sử hook."));
  }

  useEffect(load, [video.id]);

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      await generateHooks(video.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được hook.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleFavorite(jobId: number, hookId: number) {
    try {
      const updated = await toggleHookFavorite(jobId, hookId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  async function handleDelete(jobId: number) {
    try {
      await deleteHookJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  return (
    <div className="ai-form">
      {error && <div className="ai-alert ai-alert-error">{error}</div>}

      <button className="btn btn-primary" onClick={handleGenerate} disabled={disabled || generating}>
        {generating ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
        {jobs.length === 0 ? "Tạo Hook" : "Tạo lại"}
      </button>

      {jobs.length === 0 ? (
        <EmptyState icon={Sparkles} title="Chưa có hook nào" description="Bấm 'Tạo Hook' để bắt đầu." />
      ) : (
        jobs.map((job) => (
          <div key={job.id} className="ai-job-card">
            <div className="ai-job-header">
              <span className="ai-job-date">{new Date(job.created_at).toLocaleString("vi-VN")}</span>
              <button className="ai-job-delete" onClick={() => handleDelete(job.id)}>
                <Trash2 size={13} />
              </button>
            </div>
            {job.status === "failed" && job.error_message && (
              <div className="ai-alert ai-alert-error">{job.error_message}</div>
            )}
            {job.status === "completed" && (
              <ul className="ai-hook-list">
                {job.hooks.map((h) => (
                  <li key={h.id}>
                    <span>{h.text}</span>
                    <button
                      className={`ai-hook-fav${h.is_favorite ? " is-favorite" : ""}`}
                      onClick={() => handleFavorite(job.id, h.id)}
                    >
                      <Heart size={14} fill={h.is_favorite ? "currentColor" : "none"} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ---------- Caption tab ----------

const CAPTION_FIELDS: { key: keyof CaptionJob["versions"][number]; label: string }[] = [
  { key: "facebook_caption", label: "Facebook" },
  { key: "instagram_caption", label: "Instagram" },
  { key: "youtube_description", label: "YouTube" },
  { key: "pinned_comment", label: "Pinned Comment" },
  { key: "cta", label: "CTA" },
];

function CaptionTab({ video, disabled }: { video: VideoOut; disabled: boolean }) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<CaptionJob[]>([]);

  function load() {
    listCaptionJobs(video.id).then(setJobs).catch(() => setError("Không tải được lịch sử caption."));
  }

  useEffect(load, [video.id]);

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      await generateCaptions(video.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được caption.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectVersion(jobId: number, versionId: number) {
    try {
      const updated = await selectCaptionVersion(jobId, versionId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? updated : j)));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  async function handleDelete(jobId: number) {
    try {
      await deleteCaptionJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  return (
    <div className="ai-form">
      {error && <div className="ai-alert ai-alert-error">{error}</div>}

      <button className="btn btn-primary" onClick={handleGenerate} disabled={disabled || generating}>
        {generating ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
        Tạo Caption
      </button>

      {jobs.length === 0 ? (
        <EmptyState icon={Sparkles} title="Chưa có caption nào" description="Bấm 'Tạo Caption' để bắt đầu." />
      ) : (
        jobs.map((job) => (
          <div key={job.id} className="ai-job-card">
            <div className="ai-job-header">
              <span className="ai-job-date">{new Date(job.created_at).toLocaleString("vi-VN")}</span>
              <button className="ai-job-delete" onClick={() => handleDelete(job.id)}>
                <Trash2 size={13} />
              </button>
            </div>
            {job.status === "failed" && job.error_message && (
              <div className="ai-alert ai-alert-error">{job.error_message}</div>
            )}
            {job.status === "completed" && (
              <div className="ai-versions">
                {job.versions.map((v) => (
                  <div key={v.id} className={`ai-version${v.is_selected ? " ai-version--selected" : ""}`}>
                    {CAPTION_FIELDS.map((f) => (
                      <div key={String(f.key)} className="ai-caption-field">
                        <div className="ai-caption-field-label">
                          {f.label}
                          <button onClick={() => navigator.clipboard.writeText(String(v[f.key]))} title="Copy">
                            <Copy size={12} />
                          </button>
                        </div>
                        <p className="ai-version-text">{String(v[f.key])}</p>
                      </div>
                    ))}
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleSelectVersion(job.id, v.id)}
                      disabled={v.is_selected}
                    >
                      {v.is_selected ? <CheckCircle2 size={13} /> : null}
                      {v.is_selected ? "Đã chọn" : "Chọn phiên bản này"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
