import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Youtube,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  disconnectYouTubeChannel,
  fetchYouTubeChannels,
  fetchYouTubeUploads,
  getYouTubeAuthorizeUrl,
  retryYouTubeUpload,
  setChannelEnabled,
} from "../api/publishing";
import { getSettings } from "../api/settings";
import type { YouTubeChannel, YouTubeUploadJob } from "../types/publishing";
import "./PublishingPage.css";

const STATUS_LABEL: Record<YouTubeUploadJob["status"], string> = {
  pending: "Đang chờ",
  uploading: "Đang tải lên",
  completed: "Xong",
  failed: "Lỗi",
  interrupted: "Bị gián đoạn",
};

export function PublishingPage() {
  const [channels, setChannels] = useState<YouTubeChannel[]>([]);
  const [uploads, setUploads] = useState<YouTubeUploadJob[]>([]);
  const [hasOAuth, setHasOAuth] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [ch, up, s] = await Promise.all([
        fetchYouTubeChannels(),
        fetchYouTubeUploads(),
        getSettings().catch(() => null),
      ]);
      setChannels(ch);
      setUploads(up);
      setHasOAuth(s ? Boolean((s as Record<string, unknown>).has_google_oauth_client) : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu Publishing.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while any upload is active.
  useEffect(() => {
    const active = uploads.some((u) => u.status === "pending" || u.status === "uploading");
    if (active && pollRef.current == null) {
      pollRef.current = window.setInterval(load, 4000);
    } else if (!active && pollRef.current != null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current != null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [uploads, load]);

  async function handleConnect() {
    setBusy("connect");
    setError(null);
    try {
      const { authorize_url } = await getYouTubeAuthorizeUrl();
      window.open(authorize_url, "_blank", "noopener");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được link kết nối.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Publishing (YouTube)"
        subtitle="Kết nối kênh YouTube và tự động tải video hoàn chỉnh (video + tiêu đề/mô tả + thumbnail) lên."
        actions={
          <button className="btn btn-primary" onClick={handleConnect} disabled={busy === "connect" || hasOAuth === false}>
            {busy === "connect" ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
            Kết nối kênh
          </button>
        }
      />

      {error && <div className="pub-alert pub-alert-error">{error}</div>}

      {hasOAuth === false && (
        <div className="pub-alert pub-alert-warn">
          <AlertTriangle size={15} />
          <span>
            Chưa cấu hình Google OAuth. Vào <strong>Settings → YouTube Publishing</strong> nhập Client ID / Client Secret
            (tạo trong Google Cloud Console, bật YouTube Data API v3).
          </span>
        </div>
      )}

      <div className="pub-note">
        <AlertTriangle size={14} />
        <div>
          <strong>Lưu ý về giới hạn của YouTube:</strong> nếu app OAuth của bạn <em>chưa qua audit</em>, mọi video tải lên
          bị <strong>khoá ở chế độ private</strong> — bạn vào YouTube Studio bấm publish. Màn hình đồng ý (consent screen) để
          ở chế độ "Testing" thì refresh token <strong>hết hạn sau 7 ngày</strong> (phải kết nối lại). Verify app OAuth thì
          hết cả hai vấn đề.
        </div>
      </div>

      <h3 className="pub-section-title">Kênh đã kết nối</h3>
      {channels.length === 0 ? (
        <EmptyState
          icon={Youtube}
          title="Chưa có kênh nào"
          description='Bấm "Kết nối kênh" để liên kết một kênh YouTube qua Google.'
        />
      ) : (
        <div className="pub-channels">
          {channels.map((c) => (
            <div key={c.id} className="pub-channel">
              {c.thumbnail_url && <img src={c.thumbnail_url} alt="" className="pub-channel-avatar" />}
              <div className="pub-channel-info">
                <div className="pub-channel-title">{c.title}</div>
                <div className="pub-channel-meta">
                  {c.upload_count ? `${c.upload_count} video đã đăng` : "Chưa đăng video nào"}
                  {c.last_error && <span className="pub-channel-err"> · {c.last_error}</span>}
                </div>
              </div>
              <label className="pub-toggle">
                <input
                  type="checkbox"
                  checked={c.enabled}
                  onChange={async (e) => {
                    await setChannelEnabled(c.id, e.target.checked);
                    load();
                  }}
                />
                <span>{c.enabled ? "Bật" : "Tắt"}</span>
              </label>
              <button
                className="btn btn-icon"
                title="Ngắt kết nối"
                onClick={async () => {
                  if (!confirm(`Ngắt kết nối kênh "${c.title}"?`)) return;
                  await disconnectYouTubeChannel(c.id);
                  load();
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <h3 className="pub-section-title">Hàng đợi tải lên</h3>
      {uploads.length === 0 ? (
        <p className="pub-empty-hint">
          Chưa có lượt tải lên nào. Vào <strong>Produced Videos</strong>, mở 1 video và bấm "Đăng lên YouTube".
        </p>
      ) : (
        <div className="pub-table-wrap">
          <table className="pub-table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Kênh</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((u) => (
                <tr key={u.id}>
                  <td>{u.title || `Project ${u.project_id}`}</td>
                  <td>{u.channel_title}</td>
                  <td>
                    <span className={`pub-status pub-status--${u.status}`}>
                      {(u.status === "pending" || u.status === "uploading") && <Loader2 size={12} className="spin" />}
                      {STATUS_LABEL[u.status]}
                    </span>
                    {u.error_message && <div className="pub-row-err">{u.error_message}</div>}
                  </td>
                  <td className="pub-row-actions">
                    {u.watch_url && (
                      <a href={u.watch_url} target="_blank" rel="noreferrer" className="btn btn-secondary">
                        <ExternalLink size={13} /> Xem
                      </a>
                    )}
                    {(u.status === "failed" || u.status === "interrupted") && (
                      <button
                        className="btn btn-secondary"
                        onClick={async () => {
                          setBusy(`retry-${u.id}`);
                          try {
                            await retryYouTubeUpload(u.id);
                            load();
                          } catch (err) {
                            setError(err instanceof Error ? err.message : "Retry thất bại.");
                          } finally {
                            setBusy(null);
                          }
                        }}
                        disabled={busy === `retry-${u.id}`}
                      >
                        {busy === `retry-${u.id}` ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
                        Thử lại
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
