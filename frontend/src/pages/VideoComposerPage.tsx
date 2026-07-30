import { useEffect, useState } from "react";
import { Film, ArrowUp, ArrowDown, X, Loader2, FolderOpen, Music } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { createVideoComposeJob, listVideoComposeJobs, openVideoComposeJobFolder } from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import type { VideoComposeJob } from "../types/videoComposer";
import "./VideoComposerPage.css";

const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL: Record<VideoComposeJob["status"], string> = {
  queued: "Trong hàng đợi",
  merging: "Đang ghép video (chuyển cảnh swipe-left)",
  narrating: "Đang tạo giọng đọc",
  subtitling: "Đang tạo phụ đề karaoke",
  mixing_audio: "Đang trộn âm thanh",
  finalizing: "Đang hoàn thiện",
  completed: "Hoàn tất",
  failed: "Lỗi",
};

const IN_PROGRESS_STATUSES: VideoComposeJob["status"][] = [
  "queued",
  "merging",
  "narrating",
  "subtitling",
  "mixing_audio",
  "finalizing",
];

export function VideoComposerPage() {
  const [clips, setClips] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [script, setScript] = useState("");
  const [music, setMusic] = useState<File | null>(null);
  const [musicVolume, setMusicVolume] = useState(0.15);
  const [transitionDuration, setTransitionDuration] = useState(0.5);
  const [burnSubtitles, setBurnSubtitles] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [jobs, setJobs] = useState<VideoComposeJob[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await listVideoComposeJobs();
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

  function handleAddClips(fileList: FileList | null) {
    if (!fileList) return;
    setClips((prev) => [...prev, ...Array.from(fileList)]);
  }

  function moveClip(index: number, direction: -1 | 1) {
    setClips((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function removeClip(index: number) {
    setClips((prev) => prev.filter((_, i) => i !== index));
  }

  const canSubmit = clips.length > 0 && title.trim().length > 0 && script.trim().length > 0;

  async function handleSubmit() {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createVideoComposeJob({
        title: title.trim(),
        script: script.trim(),
        files: clips,
        music,
        musicVolume,
        transitionDuration,
        burnSubtitles,
      });
      const data = await listVideoComposeJobs();
      setJobs(data);
      setClips([]);
      setTitle("");
      setScript("");
      setMusic(null);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Không tạo được tác vụ ghép video.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Video Composer"
        subtitle="Ghép nhiều video, chuyển cảnh swipe-left, chèn tiêu đề, tự tạo giọng đọc + phụ đề tiếng Tây Ban Nha"
      />

      <div className="vc-form">
        <label className="vc-field">
          Tiêu đề (hiển thị cố định đầu video)
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="VD: Canal de Prueba" />
        </label>

        <label className="vc-field">
          Kịch bản (tiếng Tây Ban Nha, dùng để tạo giọng đọc + phụ đề)
          <textarea
            rows={5}
            value={script}
            onChange={(e) => setScript(e.target.value)}
            placeholder="Hola a todos, bienvenidos..."
          />
        </label>

        <div className="vc-field">
          <span>Video (theo thứ tự ghép)</span>
          <label className="vc-upload-row">
            <Film size={15} />
            <span>Thêm video...</span>
            <input type="file" accept="video/*" multiple onChange={(e) => handleAddClips(e.target.files)} />
          </label>

          {clips.length > 0 && (
            <ul className="vc-clip-list">
              {clips.map((clip, index) => (
                <li key={`${clip.name}-${index}`} className="vc-clip-row">
                  <span className="vc-clip-index">{index + 1}</span>
                  <span className="vc-clip-name">{clip.name}</span>
                  <div className="vc-clip-actions">
                    <button type="button" onClick={() => moveClip(index, -1)} disabled={index === 0} title="Lên">
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveClip(index, 1)}
                      disabled={index === clips.length - 1}
                      title="Xuống"
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button type="button" onClick={() => removeClip(index)} title="Xoá">
                      <X size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="vc-upload-row vc-music-row">
          <Music size={15} />
          <span>{music ? music.name : "Nhạc nền (tuỳ chọn)..."}</span>
          <input type="file" accept="audio/*" onChange={(e) => setMusic(e.target.files?.[0] ?? null)} />
        </label>

        <div className="vc-params">
          <label>
            Âm lượng nhạc nền
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={musicVolume}
              onChange={(e) => setMusicVolume(Number(e.target.value))}
            />
          </label>
          <label>
            Độ dài chuyển cảnh (giây)
            <input
              type="number"
              min={0}
              step={0.1}
              value={transitionDuration}
              onChange={(e) => setTransitionDuration(Number(e.target.value))}
            />
          </label>
          <label className="vc-checkbox-field">
            <input type="checkbox" checked={burnSubtitles} onChange={(e) => setBurnSubtitles(e.target.checked)} />
            Chèn phụ đề vào video
          </label>
        </div>

        {submitError && <div className="vc-alert vc-alert-error">{submitError}</div>}

        <button className="btn btn-primary" onClick={handleSubmit} disabled={!canSubmit || submitting}>
          {submitting ? <Loader2 size={16} className="spin" /> : <Film size={16} />}
          Ghép video
        </button>
      </div>

      <h2 className="vc-jobs-title">Các tác vụ đã chạy</h2>

      {jobs.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Chưa có tác vụ nào"
          description="Thêm video, nhập tiêu đề và kịch bản rồi bấm 'Ghép video' để bắt đầu."
        />
      ) : (
        <div className="vc-jobs">
          {jobs.map((job) => (
            <VideoComposeJobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </>
  );
}

function VideoComposeJobCard({ job }: { job: VideoComposeJob }) {
  const [openError, setOpenError] = useState<string | null>(null);

  async function handleOpenFolder() {
    setOpenError(null);
    try {
      await openVideoComposeJobFolder(job.id);
    } catch {
      setOpenError("Không mở được thư mục.");
    }
  }

  return (
    <div className="vc-job-card">
      <div className="vc-job-header">
        <div>
          <div className="vc-job-title">{job.title}</div>
          <div className={`vc-job-status vc-job-status--${job.status}`}>
            {IN_PROGRESS_STATUSES.includes(job.status) && <Loader2 size={13} className="spin" />}
            {STATUS_LABEL[job.status]}
            {` — ${job.clip_count} video`}
          </div>
        </div>
        {job.status === "completed" && (
          <button className="btn btn-secondary" onClick={handleOpenFolder}>
            <FolderOpen size={14} />
            Mở thư mục
          </button>
        )}
      </div>

      {openError && <div className="vc-alert vc-alert-error">{openError}</div>}

      {job.status === "failed" && job.error_message && (
        <div className="vc-alert vc-alert-error">{job.error_message}</div>
      )}

      {job.status === "completed" && job.output_media_url && (
        <video className="vc-job-preview" src={mediaUrl(job.output_media_url)} controls preload="metadata" />
      )}
    </div>
  );
}
