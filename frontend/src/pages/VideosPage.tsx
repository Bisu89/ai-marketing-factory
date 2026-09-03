import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Clapperboard,
  Clock,
  Copy,
  ExternalLink,
  Film,
  FolderOpen,
  Loader2,
  X,
  Youtube,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../features/library/components/Pagination";
import { mediaUrl } from "../api/client";
import { listProducedVideos, openProducedVideoFolder } from "../api/producedVideos";
import { fetchYouTubeChannels, uploadToYouTube } from "../api/publishing";
import type { YouTubeChannel, YouTubePrivacy } from "../types/publishing";
import type { ProducedVideo, ProducedVideoList } from "../types/producedVideo";
import "./VideosPage.css";

const PAGE_SIZE = 24;

type StatusFilter = "COMPLETED" | "FAILED" | "ALL";

function secondsLabel(value: number | null): string {
  if (value == null) return "--";
  const total = Math.round(value);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

function dateLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function VideosPage() {
  const [data, setData] = useState<ProducedVideoList | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [status, setStatus] = useState<StatusFilter>("COMPLETED");
  const [batchId, setBatchId] = useState<number | "">("");
  const [seriesId, setSeriesId] = useState<number | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);

  const [selected, setSelected] = useState<ProducedVideo | null>(null);
  const [copied, setCopied] = useState(false);
  const [actionNote, setActionNote] = useState<string | null>(null);

  const reqId = useRef(0);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [status, batchId, seriesId, debouncedSearch]);

  useEffect(() => {
    const id = ++reqId.current;
    setLoading(true);
    listProducedVideos({
      status,
      batch_id: batchId === "" ? undefined : batchId,
      series_id: seriesId === "" ? undefined : seriesId,
      q: debouncedSearch || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((result) => {
        if (id !== reqId.current) return;
        setData(result);
        setLoadError(null);
      })
      .catch((err) => {
        if (id !== reqId.current) return;
        setLoadError(err instanceof Error ? err.message : "Could not load videos.");
      })
      .finally(() => {
        if (id === reqId.current) setLoading(false);
      });
  }, [status, batchId, seriesId, debouncedSearch, page]);

  useEffect(() => {
    if (!selected) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setSelected(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  useEffect(() => {
    setCopied(false);
    setActionNote(null);
  }, [selected]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasAnyFilter = status !== "COMPLETED" || batchId !== "" || seriesId !== "" || debouncedSearch !== "";

  const batchOptions = useMemo(() => data?.batches ?? [], [data]);
  const seriesOptions = useMemo(() => data?.series ?? [], [data]);

  async function handleCopyPath(video: ProducedVideo) {
    if (!video.output_path) return;
    try {
      await navigator.clipboard.writeText(video.output_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setActionNote("Không copy được — trình duyệt chặn clipboard.");
    }
  }

  async function handleOpenFolder(video: ProducedVideo) {
    try {
      await openProducedVideoFolder(video.render_job_id);
      setActionNote("Đã mở thư mục.");
    } catch (err) {
      setActionNote(err instanceof Error ? err.message : "Không mở được thư mục.");
    }
  }

  return (
    <>
      <PageHeader
        title="Videos"
        subtitle="Mọi video đã render từ Video Factory và Video Composer — lọc theo batch, series hoặc trạng thái, xem lại và lấy đường dẫn file."
      />

      <div className="videos-toolbar">
        <div className="videos-tabs">
          {(["COMPLETED", "FAILED", "ALL"] as StatusFilter[]).map((s) => (
            <button
              key={s}
              className={`videos-tab${status === s ? " active" : ""}`}
              onClick={() => setStatus(s)}
            >
              {s === "COMPLETED" ? "Hoàn thành" : s === "FAILED" ? "Lỗi" : "Tất cả"}
            </button>
          ))}
        </div>

        <div className="videos-filters">
          <select value={batchId} onChange={(e) => setBatchId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Mọi batch</option>
            {batchOptions.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.count})
              </option>
            ))}
          </select>
          <select value={seriesId} onChange={(e) => setSeriesId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Mọi series</option>
            {seriesOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.count})
              </option>
            ))}
          </select>
          <input
            type="search"
            placeholder="Tìm theo tiêu đề…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loadError && <div className="videos-alert">{loadError}</div>}

      {loading && !data ? (
        <div className="videos-loading">
          <Loader2 size={20} className="spin" /> Đang tải…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Film}
          title={hasAnyFilter ? "Không có video khớp bộ lọc" : "Chưa có video nào"}
          description={
            hasAnyFilter
              ? "Thử bỏ bớt bộ lọc hoặc đổi trạng thái."
              : "Render video từ Video Factory hoặc Batch, xong sẽ xuất hiện ở đây."
          }
        />
      ) : (
        <>
          <div className={`videos-grid${loading ? " is-loading" : ""}`}>
            {items.map((video) => (
              <button key={video.render_job_id} className="video-card" onClick={() => setSelected(video)}>
                <div className="video-card-thumb">
                  {video.thumbnail_url ? (
                    <img src={mediaUrl(video.thumbnail_url)} alt="" loading="lazy" />
                  ) : (
                    <div className="video-card-thumb-fallback">
                      <Clapperboard size={22} />
                    </div>
                  )}
                  {video.duration_sec != null && (
                    <span className="video-card-duration">{secondsLabel(video.duration_sec)}</span>
                  )}
                  {video.job_status !== "COMPLETED" && (
                    <span className={`video-card-status status-${video.job_status.toLowerCase()}`}>
                      {video.job_status}
                    </span>
                  )}
                </div>
                <div className="video-card-body">
                  <span className="video-card-title">{video.title}</span>
                  <span className="video-card-sub">
                    {video.batch_name ?? video.series_name ?? "Đơn lẻ"} · {dateLabel(video.created_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>

          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} itemLabel="video" />
        </>
      )}

      {selected && (
        <div className="videos-drawer-overlay" onClick={() => setSelected(null)}>
          <aside className="videos-drawer" onClick={(e) => e.stopPropagation()}>
            <button className="videos-drawer-close" onClick={() => setSelected(null)} aria-label="Đóng">
              <X size={16} />
            </button>

            <div className="videos-drawer-player">
              {selected.output_media_url ? (
                <video
                  key={selected.render_job_id}
                  src={mediaUrl(selected.output_media_url)}
                  controls
                  playsInline
                />
              ) : (
                <div className="videos-drawer-player-empty">Không có file để xem</div>
              )}
            </div>

            <div className="videos-drawer-body">
              <h2 className="videos-drawer-title">{selected.title}</h2>
              {selected.description && <p className="videos-drawer-desc">{selected.description}</p>}

              {selected.hashtags.length > 0 && (
                <div className="videos-drawer-tags">
                  {selected.hashtags.map((h) => (
                    <span key={h} className="videos-drawer-tag">
                      {h.startsWith("#") ? h : `#${h}`}
                    </span>
                  ))}
                </div>
              )}

              <dl className="videos-drawer-meta">
                <div>
                  <dt>Trạng thái</dt>
                  <dd>{selected.job_status}</dd>
                </div>
                <div>
                  <dt>
                    <Clock size={12} /> Thời lượng
                  </dt>
                  <dd>{secondsLabel(selected.duration_sec)}</dd>
                </div>
                <div>
                  <dt>Độ phân giải</dt>
                  <dd>{selected.width && selected.height ? `${selected.width}×${selected.height}` : "--"}</dd>
                </div>
                <div>
                  <dt>Dung lượng</dt>
                  <dd>{selected.output_size_mb != null ? `${selected.output_size_mb.toFixed(1)} MB` : "--"}</dd>
                </div>
                <div>
                  <dt>Render mất</dt>
                  <dd>
                    {selected.render_time_seconds != null ? `${selected.render_time_seconds.toFixed(1)}s` : "--"}
                  </dd>
                </div>
                <div>
                  <dt>Ngày tạo</dt>
                  <dd>{dateLabel(selected.created_at)}</dd>
                </div>
                {selected.batch_name && (
                  <div>
                    <dt>Batch</dt>
                    <dd>
                      <Link to={`/batches/${selected.batch_id}`}>{selected.batch_name}</Link>
                    </dd>
                  </div>
                )}
                {selected.series_name && (
                  <div>
                    <dt>Series</dt>
                    <dd>
                      <Link to={`/series/${selected.series_id}`}>{selected.series_name}</Link>
                    </dd>
                  </div>
                )}
              </dl>

              {selected.output_path && (
                <div className="videos-drawer-path">
                  <code>{selected.output_path}</code>
                </div>
              )}

              <div className="videos-drawer-actions">
                {selected.project_id != null && (
                  <Link className="btn btn-secondary" to={`/video-factory?project=${selected.project_id}`}>
                    <ExternalLink size={14} /> Mở trong Video Factory
                  </Link>
                )}
                <button
                  className="btn btn-secondary"
                  onClick={() => handleCopyPath(selected)}
                  disabled={!selected.output_path}
                >
                  <Copy size={14} /> {copied ? "Đã copy" : "Copy đường dẫn"}
                </button>
                <button className="btn btn-secondary" onClick={() => handleOpenFolder(selected)}>
                  <FolderOpen size={14} /> Mở thư mục
                </button>
                {selected.project_id != null && selected.job_status === "COMPLETED" && (
                  <YouTubeUploadButton projectId={selected.project_id} />
                )}
              </div>
              {actionNote && <p className="videos-drawer-note">{actionNote}</p>}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

function YouTubeUploadButton({ projectId }: { projectId: number }) {
  const [open, setOpen] = useState(false);
  const [channels, setChannels] = useState<YouTubeChannel[] | null>(null);
  const [channelId, setChannelId] = useState<number | "">("");
  const [privacy, setPrivacy] = useState<YouTubePrivacy>("private");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function openPicker() {
    setOpen(true);
    setMsg(null);
    if (channels == null) {
      try {
        const list = await fetchYouTubeChannels();
        setChannels(list);
        const firstEnabled = list.find((c) => c.enabled);
        if (firstEnabled) setChannelId(firstEnabled.id);
      } catch (err) {
        setMsg(err instanceof Error ? err.message : "Không tải được danh sách kênh.");
      }
    }
  }

  async function handleUpload() {
    if (channelId === "" || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await uploadToYouTube({ project_id: projectId, channel_id: channelId, privacy });
      setMsg("Đã đưa vào hàng đợi tải lên. Xem tiến độ ở trang Publishing.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Tải lên thất bại.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="btn btn-secondary" onClick={openPicker}>
        <Youtube size={14} /> Đăng lên YouTube
      </button>
      {open && (
        <div className="videos-drawer-overlay" onClick={() => setOpen(false)}>
          <div className="videos-yt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="videos-yt-modal-header">
              <h3>Đăng lên YouTube</h3>
              <button className="btn btn-icon" onClick={() => setOpen(false)}>
                <X size={15} />
              </button>
            </div>
            {channels != null && channels.length === 0 ? (
              <p className="videos-drawer-note">
                Chưa kết nối kênh nào. Vào <Link to="/publishing">Publishing</Link> để kết nối.
              </p>
            ) : (
              <>
                <label className="videos-yt-field">
                  <span>Kênh</span>
                  <select
                    value={channelId}
                    onChange={(e) => setChannelId(e.target.value === "" ? "" : Number(e.target.value))}
                  >
                    <option value="">— chọn kênh —</option>
                    {(channels ?? []).map((c) => (
                      <option key={c.id} value={c.id} disabled={!c.enabled}>
                        {c.title}
                        {c.enabled ? "" : " (tắt)"}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="videos-yt-field">
                  <span>Chế độ</span>
                  <select value={privacy} onChange={(e) => setPrivacy(e.target.value as YouTubePrivacy)}>
                    <option value="private">Private</option>
                    <option value="unlisted">Unlisted</option>
                    <option value="public">Public</option>
                  </select>
                </label>
                <p className="videos-drawer-note">
                  App OAuth chưa audit thì YouTube vẫn khoá video ở private dù chọn gì — vào Studio bấm publish.
                </p>
                <div className="videos-yt-actions">
                  <button className="btn btn-secondary" onClick={() => setOpen(false)}>
                    Đóng
                  </button>
                  <button className="btn btn-primary" onClick={handleUpload} disabled={busy || channelId === ""}>
                    {busy ? <Loader2 size={14} className="spin" /> : <Youtube size={14} />}
                    Tải lên
                  </button>
                </div>
              </>
            )}
            {msg && <p className="videos-drawer-note">{msg}</p>}
          </div>
        </div>
      )}
    </>
  );
}
