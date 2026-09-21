import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, BookOpen, Loader2, RotateCcw, Trash2, Upload, Download, Wand2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  createEpisode,
  createEpisodeFromFile,
  deleteAsset,
  deleteEpisode,
  episodeFileUrl,
  listAssets,
  listEpisodes,
  retryEpisode,
  uploadAsset,
} from "../api/storyteller";
import { VOICE_OPTIONS } from "../types/videoFactory";
import type { StorytellerAsset, StorytellerEpisode, StorytellerLayout } from "../types/storyteller";
import "./StorytellerPage.css";

const POLL_INTERVAL_MS = 2000;
const PENDING_STATUSES = new Set(["pending", "narrating", "compositing"]);

const RATE_OPTIONS = [
  { value: "-20%", label: "Chậm" },
  { value: "+0%", label: "Bình thường" },
  { value: "+20%", label: "Nhanh" },
  { value: "+40%", label: "Rất nhanh" },
];

const STATUS_LABEL: Record<string, string> = {
  pending: "Chờ xử lý",
  narrating: "Đang đọc",
  compositing: "Đang ghép video",
  completed: "Hoàn tất",
  failed: "Lỗi",
};

function formatDuration(sec: number | null): string {
  if (sec == null) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function StorytellerPage() {
  const [episodes, setEpisodes] = useState<StorytellerEpisode[]>([]);
  const [backgrounds, setBackgrounds] = useState<StorytellerAsset[]>([]);
  const [avatars, setAvatars] = useState<StorytellerAsset[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [voice, setVoice] = useState(
    VOICE_OPTIONS.find((v) => v.value === "vi-VN-HoaiMyNeural")?.value ?? VOICE_OPTIONS[0].value,
  );
  const [narrationRate, setNarrationRate] = useState("+0%");
  const [burnCaptions, setBurnCaptions] = useState(true);
  const [layout, setLayout] = useState<StorytellerLayout>("single");
  const [backgroundAssetId, setBackgroundAssetId] = useState<number | "">("");
  const [avatarAssetId, setAvatarAssetId] = useState<number | "">("");
  const [leftAssetId, setLeftAssetId] = useState<number | "">("");
  const [middleAssetId, setMiddleAssetId] = useState<number | "">("");
  const [rightAssetId, setRightAssetId] = useState<number | "">("");
  const [slideAssetIds, setSlideAssetIds] = useState<number[]>([]);
  const [disclaimerText, setDisclaimerText] = useState("");
  const [storyTitle, setStoryTitle] = useState("");
  const [storyAuthor, setStoryAuthor] = useState("");
  const [storyCharacter, setStoryCharacter] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function refresh() {
    listEpisodes().then(setEpisodes).catch(() => {});
  }

  useEffect(() => {
    refresh();
    listAssets("background").then(setBackgrounds).catch(() => {});
    listAssets("avatar").then(setAvatars).catch(() => {});
  }, []);

  useEffect(() => {
    const hasActive = episodes.some((e) => PENDING_STATUSES.has(e.status));
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [episodes]);

  const imagePool = [...backgrounds, ...avatars].filter((a) => a.media_type === "image");

  function addSlide(id: number) {
    setSlideAssetIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }
  function removeSlide(id: number) {
    setSlideAssetIds((prev) => prev.filter((x) => x !== id));
  }
  function moveSlide(index: number, dir: -1 | 1) {
    setSlideAssetIds((prev) => {
      const target = index + dir;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  const slideshowNeedsMoreImages = layout === "slideshow" && slideAssetIds.length < 2;

  async function handleSubmit() {
    if (!title.trim() || submitting) return;
    if (!uploadFile && !scriptText.trim()) return;
    if (slideshowNeedsMoreImages) return;
    setSubmitting(true);
    setError(null);
    try {
      const shared = {
        title: title.trim(),
        voice,
        narration_rate: narrationRate,
        burn_captions: burnCaptions,
        layout,
        background_asset_id: backgroundAssetId === "" ? null : backgroundAssetId,
        avatar_asset_id: avatarAssetId === "" ? null : avatarAssetId,
        left_asset_id: leftAssetId === "" ? null : leftAssetId,
        middle_asset_id: middleAssetId === "" ? null : middleAssetId,
        right_asset_id: rightAssetId === "" ? null : rightAssetId,
        slide_asset_ids: layout === "slideshow" ? slideAssetIds : null,
        disclaimer_text: disclaimerText.trim() || null,
        story_title: storyTitle.trim() || null,
        story_author: storyAuthor.trim() || null,
        story_character: storyCharacter.trim() || null,
      };
      if (uploadFile) {
        await createEpisodeFromFile(uploadFile, shared);
      } else {
        await createEpisode({ ...shared, script_text: scriptText });
      }
      setTitle("");
      setScriptText("");
      setUploadFile(null);
      setSlideAssetIds([]);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tạo được tập.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(id: number) {
    try {
      await retryEpisode(id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thử lại được.");
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Xoá tập này?")) return;
    try {
      await deleteEpisode(id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xoá được.");
    }
  }

  async function handleUploadAsset(kind: "background" | "avatar", file: File) {
    try {
      const asset = await uploadAsset(kind, file.name.replace(/\.[^.]+$/, ""), file);
      if (kind === "background") setBackgrounds((prev) => [asset, ...prev]);
      else setAvatars((prev) => [asset, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải lên được clip.");
    }
  }

  async function handleDeleteAsset(kind: "background" | "avatar", id: number) {
    try {
      await deleteAsset(id);
      if (kind === "background") setBackgrounds((prev) => prev.filter((a) => a.id !== id));
      else setAvatars((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xoá được clip.");
    }
  }

  return (
    <>
      <PageHeader
        title="Kể Truyện"
        subtitle="Dán hoặc upload kịch bản (viết ở ngoài) — tool tự đọc, ghép nền, phụ đề, không dùng AI"
      />

      {error && <div className="st-alert st-alert-error">{error}</div>}

      <div className="st-card">
        <h3 className="st-card-title">Tạo tập mới</h3>
        <input
          className="st-input"
          type="text"
          placeholder="Tên tập, vd: Chương 1 - Khởi đầu"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <textarea
          className="st-textarea"
          placeholder="Dán kịch bản vào đây..."
          value={scriptText}
          onChange={(e) => setScriptText(e.target.value)}
          disabled={!!uploadFile}
          rows={8}
        />

        <div className="st-file-row">
          <label className="btn btn-secondary st-file-label">
            <Upload size={14} />
            {uploadFile ? uploadFile.name : "Hoặc chọn file .txt"}
            <input
              type="file"
              accept=".txt"
              hidden
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {uploadFile && (
            <button className="btn btn-secondary" onClick={() => setUploadFile(null)}>
              Bỏ file
            </button>
          )}
        </div>

        <div className="st-options-row">
          <select className="st-select" value={voice} onChange={(e) => setVoice(e.target.value)}>
            {VOICE_OPTIONS.map((v) => (
              <option key={v.value} value={v.value}>
                Giọng: {v.label}
              </option>
            ))}
          </select>

          <select className="st-select" value={narrationRate} onChange={(e) => setNarrationRate(e.target.value)}>
            {RATE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                Tốc độ: {r.label}
              </option>
            ))}
          </select>

          <label className="st-checkbox">
            <input type="checkbox" checked={burnCaptions} onChange={(e) => setBurnCaptions(e.target.checked)} />
            Ghi phụ đề
          </label>

          <select className="st-select" value={layout} onChange={(e) => setLayout(e.target.value as StorytellerLayout)}>
            <option value="single">Bố cục: 1 nền + avatar góc</option>
            <option value="triptych">Bố cục: 3 cột chia màn hình</option>
            <option value="slideshow">Bố cục: slideshow nhiều ảnh (zoom Ken Burns)</option>
          </select>
        </div>

        {layout === "single" ? (
          <div className="st-options-row">
            <select
              className="st-select"
              value={backgroundAssetId}
              onChange={(e) => setBackgroundAssetId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">Nền: mặc định (màu trơn)</option>
              {backgrounds.map((a) => (
                <option key={a.id} value={a.id}>
                  Nền: {a.name}
                </option>
              ))}
            </select>

            <select
              className="st-select"
              value={avatarAssetId}
              onChange={(e) => setAvatarAssetId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">Avatar: không có</option>
              {avatars.map((a) => (
                <option key={a.id} value={a.id}>
                  Avatar: {a.name}
                </option>
              ))}
            </select>
          </div>
        ) : layout === "triptych" ? (
          <div className="st-options-row">
            <select className="st-select" value={leftAssetId} onChange={(e) => setLeftAssetId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Cột trái: mặc định</option>
              {[...avatars, ...backgrounds].map((a) => (
                <option key={a.id} value={a.id}>
                  Trái: {a.name}
                </option>
              ))}
            </select>
            <select className="st-select" value={middleAssetId} onChange={(e) => setMiddleAssetId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Cột giữa: mặc định</option>
              {[...backgrounds, ...avatars].map((a) => (
                <option key={a.id} value={a.id}>
                  Giữa: {a.name}
                </option>
              ))}
            </select>
            <select className="st-select" value={rightAssetId} onChange={(e) => setRightAssetId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Cột phải: mặc định</option>
              {[...backgrounds, ...avatars].map((a) => (
                <option key={a.id} value={a.id}>
                  Phải: {a.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="st-slideshow-picker">
            <div className="st-file-row">
              <select
                className="st-select"
                value=""
                onChange={(e) => {
                  if (e.target.value) addSlide(Number(e.target.value));
                }}
              >
                <option value="">+ Thêm ảnh vào slideshow...</option>
                {imagePool
                  .filter((a) => !slideAssetIds.includes(a.id))
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </select>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSlideAssetIds(imagePool.map((a) => a.id))}
                disabled={imagePool.length === 0}
                title="Dùng thử toàn bộ ảnh có sẵn trong thư viện -- không cần tự gen ảnh mới"
              >
                <Wand2 size={14} /> Test bằng ảnh có sẵn ({imagePool.length})
              </button>
            </div>
            {slideAssetIds.length === 0 ? (
              <p className="st-asset-empty">Chưa chọn ảnh nào -- cần ít nhất 2 ảnh, theo đúng thứ tự xuất hiện.</p>
            ) : (
              <ul className="st-asset-list">
                {slideAssetIds.map((id, i) => {
                  const asset = imagePool.find((a) => a.id === id);
                  return (
                    <li key={id}>
                      <span>
                        {i + 1}. {asset?.name ?? `#${id}`}
                      </span>
                      <button className="st-asset-remove" onClick={() => moveSlide(i, -1)} disabled={i === 0} title="Lên trước">
                        <ArrowUp size={13} />
                      </button>
                      <button
                        className="st-asset-remove"
                        onClick={() => moveSlide(i, 1)}
                        disabled={i === slideAssetIds.length - 1}
                        title="Xuống sau"
                      >
                        <ArrowDown size={13} />
                      </button>
                      <button className="st-asset-remove" onClick={() => removeSlide(id)} title="Xoá">
                        <Trash2 size={13} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {slideshowNeedsMoreImages && slideAssetIds.length > 0 && (
              <p className="st-asset-empty">Cần thêm ít nhất {2 - slideAssetIds.length} ảnh nữa.</p>
            )}
          </div>
        )}

        <input
          className="st-input"
          type="text"
          placeholder="Dòng miễn trừ trách nhiệm (tuỳ chọn), vd: Nội dung chỉ mang tính giải trí..."
          value={disclaimerText}
          onChange={(e) => setDisclaimerText(e.target.value)}
        />

        <div className="st-options-row">
          <input
            className="st-input st-story-info-input"
            type="text"
            placeholder="Tên truyện (tuỳ chọn)"
            value={storyTitle}
            onChange={(e) => setStoryTitle(e.target.value)}
          />
          <input
            className="st-input st-story-info-input"
            type="text"
            placeholder="Tác giả (tuỳ chọn)"
            value={storyAuthor}
            onChange={(e) => setStoryAuthor(e.target.value)}
          />
          <input
            className="st-input st-story-info-input"
            type="text"
            placeholder="Nhân vật chính (tuỳ chọn)"
            value={storyCharacter}
            onChange={(e) => setStoryCharacter(e.target.value)}
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={submitting || !title.trim() || (!uploadFile && !scriptText.trim()) || slideshowNeedsMoreImages}
        >
          {submitting ? <Loader2 size={16} className="spin" /> : <BookOpen size={16} />}
          Tạo & bắt đầu đọc
        </button>
      </div>

      <div className="st-card">
        <h3 className="st-card-title">Clip nền / avatar</h3>
        <div className="st-asset-cols">
          <AssetColumn kind="background" label="Nền lặp" assets={backgrounds} onUpload={handleUploadAsset} onDelete={handleDeleteAsset} />
          <AssetColumn kind="avatar" label="Avatar (tự tách nền màu)" assets={avatars} onUpload={handleUploadAsset} onDelete={handleDeleteAsset} />
        </div>
      </div>

      <h3 className="st-card-title">Các tập</h3>
      {episodes.length === 0 ? (
        <EmptyState icon={BookOpen} title="Chưa có tập nào" description="Tạo tập đầu tiên ở form phía trên." />
      ) : (
        <div className="st-episode-list">
          {episodes.map((ep) => (
            <div key={ep.id} className="st-episode-row">
              <div className="st-episode-main">
                <span className="st-episode-title">{ep.title}</span>
                <span className="st-episode-meta">
                  {ep.word_count.toLocaleString()} từ · {formatDuration(ep.duration_sec)}
                </span>
              </div>
              <div className="st-episode-status">
                <span className={`st-status-badge st-status--${ep.status}`}>
                  {PENDING_STATUSES.has(ep.status) && <Loader2 size={12} className="spin" />}
                  {STATUS_LABEL[ep.status] ?? ep.status}
                </span>
                {ep.progress_stage && <span className="st-progress-stage">{ep.progress_stage}</span>}
                {ep.error_message && <span className="st-error-text">{ep.error_message}</span>}
              </div>
              <div className="st-episode-actions">
                {ep.status === "completed" && (
                  <a className="btn btn-secondary" href={episodeFileUrl(ep.id)} target="_blank" rel="noreferrer">
                    <Download size={14} /> Xem/Tải
                  </a>
                )}
                {ep.status === "failed" && (
                  <button className="btn btn-secondary" onClick={() => handleRetry(ep.id)}>
                    <RotateCcw size={14} /> Thử lại
                  </button>
                )}
                <button className="btn btn-secondary" onClick={() => handleDelete(ep.id)}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function AssetColumn({
  kind,
  label,
  assets,
  onUpload,
  onDelete,
}: {
  kind: "background" | "avatar";
  label: string;
  assets: StorytellerAsset[];
  onUpload: (kind: "background" | "avatar", file: File) => void;
  onDelete: (kind: "background" | "avatar", id: number) => void;
}) {
  return (
    <div className="st-asset-col">
      <div className="st-asset-col-header">
        <span>{label}</span>
        <label className="btn btn-secondary">
          <Upload size={13} /> Tải lên
          <input
            type="file"
            accept="video/*,image/*"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(kind, file);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      {assets.length === 0 ? (
        <p className="st-asset-empty">Chưa có clip nào</p>
      ) : (
        <ul className="st-asset-list">
          {assets.map((a) => (
            <li key={a.id}>
              <span>{a.name}</span>
              {a.width && a.height && (
                <span className="st-asset-dim">
                  {a.width}×{a.height}
                </span>
              )}
              <button className="st-asset-remove" onClick={() => onDelete(kind, a.id)} title="Xoá">
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
