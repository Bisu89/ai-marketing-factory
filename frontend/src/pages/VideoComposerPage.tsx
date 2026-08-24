import { useEffect, useState } from "react";
import { Film, ArrowUp, ArrowDown, X, Loader2, FolderOpen, FolderInput, Music } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  createChineseDramaJob,
  createVideoComposeJob,
  listVideoComposeJobs,
  openVideoComposeJobFolder,
  pickVideoComposeOutputFolder,
} from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import type { VideoComposeJob } from "../types/videoComposer";
import "./VideoComposerPage.css";

const POLL_INTERVAL_MS = 2000;

const VOICE_OPTIONS: { value: string; label: string }[] = [
  { value: "en-US-GuyNeural", label: "Tiếng Anh (Nam)" },
  { value: "en-US-AriaNeural", label: "Tiếng Anh (Nữ)" },
  { value: "es-ES-AlvaroNeural", label: "Tiếng Tây Ban Nha (Nam)" },
  { value: "es-ES-ElviraNeural", label: "Tiếng Tây Ban Nha (Nữ)" },
  { value: "vi-VN-NamMinhNeural", label: "Tiếng Việt (Nam)" },
  { value: "vi-VN-HoaiMyNeural", label: "Tiếng Việt (Nữ)" },
];

const STATUS_LABEL: Record<VideoComposeJob["status"], string> = {
  queued: "Trong hàng đợi",
  transcribing: "Đang nhận diện giọng nói tiếng Trung...",
  translating: "Đang dịch & viết tiêu đề...",
  rendering_beats: "Đang dựng cảnh",
  merging: "Đang ghép video (chuyển cảnh swipe-left)",
  narrating: "Đang tạo giọng đọc",
  subtitling: "Đang tạo phụ đề karaoke",
  mixing_audio: "Đang trộn âm thanh",
  finalizing: "Đang hoàn thiện",
  composing_final: "Đang dựng video cuối cùng",
  validating: "Đang kiểm tra kết quả",
  completed: "Hoàn tất",
  failed: "Lỗi",
  cancelled: "Đã huỷ",
};

const IN_PROGRESS_STATUSES: VideoComposeJob["status"][] = [
  "queued",
  "transcribing",
  "translating",
  "rendering_beats",
  "merging",
  "narrating",
  "subtitling",
  "mixing_audio",
  "finalizing",
  "validating",
];

type ComposerMode = "standard" | "chinese_drama";

export function VideoComposerPage() {
  const [mode, setMode] = useState<ComposerMode>("standard");
  const [dubFile, setDubFile] = useState<File | null>(null);
  const [dubDragOver, setDubDragOver] = useState(false);

  const [clips, setClips] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [script, setScript] = useState("");
  const [voice, setVoice] = useState(VOICE_OPTIONS[0].value);
  const [music, setMusic] = useState<File | null>(null);
  const [musicVolume, setMusicVolume] = useState(0.15);
  const [transitionDuration, setTransitionDuration] = useState(0.5);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [outputDir, setOutputDir] = useState("");
  const [pickingFolder, setPickingFolder] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [jobs, setJobs] = useState<VideoComposeJob[]>([]);

  const [clipsDragOver, setClipsDragOver] = useState(false);
  const [musicDragOver, setMusicDragOver] = useState(false);

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
    // Dropped content isn't pre-filtered by an `accept` attribute the way
    // the file-picker dialog is, so filter out anything that isn't a video
    // (e.g. if a folder containing mixed files got dragged in).
    const videos = Array.from(fileList).filter((f) => f.type.startsWith("video/") || f.type === "");
    setClips((prev) => [...prev, ...videos]);
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
        voice,
        files: clips,
        music,
        musicVolume,
        transitionDuration,
        burnSubtitles,
        outputDir: outputDir.trim() || undefined,
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

  async function handleSubmitChineseDrama() {
    if (!dubFile || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createChineseDramaJob(dubFile, outputDir.trim() || undefined);
      const data = await listVideoComposeJobs();
      setJobs(data);
      setDubFile(null);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Không tạo được tác vụ Chinese Drama.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePickFolder() {
    setPickingFolder(true);
    setSubmitError(null);
    try {
      const path = await pickVideoComposeOutputFolder();
      if (path) setOutputDir(path);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Không mở được hộp thoại chọn thư mục.");
    } finally {
      setPickingFolder(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Video Composer"
        subtitle="Ghép nhiều video, chuyển cảnh swipe-left, chèn tiêu đề, tự tạo giọng đọc + phụ đề"
      />

      <div className="vc-mode-toggle">
        <button
          type="button"
          className={`vc-mode-btn${mode === "standard" ? " vc-mode-btn--active" : ""}`}
          onClick={() => setMode("standard")}
        >
          Standard
        </button>
        <button
          type="button"
          className={`vc-mode-btn${mode === "chinese_drama" ? " vc-mode-btn--active" : ""}`}
          onClick={() => setMode("chinese_drama")}
        >
          Chinese Drama → Vietnamese Shorts
        </button>
      </div>

      <div className="vc-form">
        {mode === "chinese_drama" ? (
          <div className="vc-field">
            <span>Video phim Trung Quốc (1 file)</span>
            <p className="vc-hint">
              Tự động: nhận diện lời thoại tiếng Trung, dịch sang tiếng Việt, viết tiêu đề + hook, lồng giọng đọc
              tiếng Việt, chèn phụ đề, cắt dọc 9:16.
            </p>
            <label
              className={`vc-upload-row${dubDragOver ? " vc-drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDubDragOver(true);
              }}
              onDragLeave={() => setDubDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDubDragOver(false);
                const file = e.dataTransfer.files?.[0];
                if (file && (file.type.startsWith("video/") || file.type === "")) setDubFile(file);
              }}
            >
              <Film size={15} />
              <span>{dubFile ? dubFile.name : "Chọn video... (hoặc kéo thả file vào đây)"}</span>
              <input type="file" accept="video/*" onChange={(e) => setDubFile(e.target.files?.[0] ?? null)} />
            </label>
          </div>
        ) : (
          <>
            <label className="vc-field">
              Tiêu đề (hiển thị cố định đầu video)
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="VD: Canal de Prueba" />
            </label>

            <label className="vc-field">
              Kịch bản (dùng để tạo giọng đọc + phụ đề)
              <textarea
                rows={5}
                value={script}
                onChange={(e) => setScript(e.target.value)}
                placeholder="Hi everyone, welcome..."
              />
            </label>

            <label className="vc-field">
              Giọng đọc
              <select value={voice} onChange={(e) => setVoice(e.target.value)}>
                {VOICE_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="vc-field">
              <span>Video (theo thứ tự ghép)</span>
              <label
                className={`vc-upload-row${clipsDragOver ? " vc-drag-over" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setClipsDragOver(true);
                }}
                onDragLeave={() => setClipsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setClipsDragOver(false);
                  handleAddClips(e.dataTransfer.files);
                }}
              >
                <Film size={15} />
                <span>Thêm video... (hoặc kéo thả file vào đây)</span>
                <input type="file" accept="video/*" multiple onChange={(e) => handleAddClips(e.target.files)} />
              </label>

              {clips.length > 0 && (
                <ul className="vc-clip-list">
                  {clips.map((clip, index) => (
                    <li key={`${clip.name}-${index}`} className="vc-clip-row">
                      <span className="vc-clip-index">{index + 1}</span>
                      <ClipThumbnail file={clip} />
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

            <label
              className={`vc-upload-row vc-music-row${musicDragOver ? " vc-drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setMusicDragOver(true);
              }}
              onDragLeave={() => setMusicDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setMusicDragOver(false);
                const file = e.dataTransfer.files?.[0];
                if (file && (file.type.startsWith("audio/") || file.type === "")) setMusic(file);
              }}
            >
              <Music size={15} />
              <span>{music ? music.name : "Nhạc nền (tuỳ chọn, hoặc kéo thả vào đây)..."}</span>
              <input type="file" accept="audio/*" onChange={(e) => setMusic(e.target.files?.[0] ?? null)} />
            </label>
          </>
        )}

        <label className="vc-field">
          Thư mục lưu kết quả (tuỳ chọn, để trống dùng mặc định)
          <div className="vc-output-dir-row">
            <input
              type="text"
              placeholder="VD: D:\VideoDaGhep"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
            />
            <button type="button" className="btn btn-secondary" onClick={handlePickFolder} disabled={pickingFolder}>
              {pickingFolder ? <Loader2 size={14} className="spin" /> : <FolderInput size={14} />}
              Chọn thư mục...
            </button>
          </div>
        </label>

        {mode === "standard" && (
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
        )}

        {submitError && <div className="vc-alert vc-alert-error">{submitError}</div>}

        {mode === "chinese_drama" ? (
          <button className="btn btn-primary" onClick={handleSubmitChineseDrama} disabled={!dubFile || submitting}>
            {submitting ? <Loader2 size={16} className="spin" /> : <Film size={16} />}
            Tạo video
          </button>
        ) : (
          <button className="btn btn-primary" onClick={handleSubmit} disabled={!canSubmit || submitting}>
            {submitting ? <Loader2 size={16} className="spin" /> : <Film size={16} />}
            Ghép video
          </button>
        )}
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

function ClipThumbnail({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    // Create AND revoke inside the same effect (not a useState lazy
    // initializer + separate cleanup) so React 19 StrictMode's dev-only
    // mount->cleanup->mount replay can't revoke a blob URL that a later
    // invocation is still relying on -- each invocation's URL is only ever
    // torn down by that same invocation's own cleanup.
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!url) {
    return <div className="vc-clip-thumb" />;
  }

  return (
    <video
      className="vc-clip-thumb"
      src={url}
      muted
      playsInline
      preload="metadata"
      // Chrome/Edge often render a blank frame at t=0 until an explicit
      // seek happens -- nudging to 0.1s forces a real decoded frame to show
      // as the thumbnail instead of a black box.
      onLoadedMetadata={(e) => {
        e.currentTarget.currentTime = 0.1;
      }}
    />
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
