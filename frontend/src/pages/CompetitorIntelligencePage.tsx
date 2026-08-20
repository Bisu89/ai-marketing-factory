import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, RefreshCw, Sparkles, Trash2, Unlink } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  analyzeCompetitorVideo,
  createCompetitorVideo,
  deleteCompetitorVideo,
  disconnectTikTokAccount,
  getCompetitorVideos,
  getTikTokAccount,
  getTikTokAuthorizeUrl,
  getTikTokVideos,
  triggerTikTokSync,
} from "../api/competitorIntelligence";
import type { CompetitorVideo, TikTokAccount, TikTokVideo } from "../types/competitorIntelligence";
import "./CompetitorIntelligencePage.css";

function num(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("vi-VN");
}

const PATTERN_FIELDS: { key: keyof CompetitorVideo; label: string }[] = [
  { key: "emotional_pattern", label: "Emotional Pattern" },
  { key: "hook_structure", label: "Hook Structure" },
  { key: "conflict_type", label: "Conflict Type" },
  { key: "character_type", label: "Character Type" },
  { key: "ending_style", label: "Ending Style" },
  { key: "estimated_format", label: "Estimated Format" },
];

export function CompetitorIntelligencePage() {
  const [account, setAccount] = useState<TikTokAccount | null>(null);
  const [videos, setVideos] = useState<TikTokVideo[]>([]);
  const [accountLoading, setAccountLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const [competitors, setCompetitors] = useState<CompetitorVideo[]>([]);
  const [competitorsLoading, setCompetitorsLoading] = useState(true);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [handle, setHandle] = useState("");
  const [titleCaption, setTitleCaption] = useState("");
  const [durationSec, setDurationSec] = useState("");
  const [notes, setNotes] = useState("");

  function refreshAccount() {
    setAccountLoading(true);
    Promise.all([getTikTokAccount(), getTikTokVideos()])
      .then(([acc, vids]) => {
        setAccount(acc);
        setVideos(vids);
      })
      .catch((err) => setAccountError(err instanceof Error ? err.message : "Không tải được trạng thái TikTok."))
      .finally(() => setAccountLoading(false));
  }

  function refreshCompetitors() {
    setCompetitorsLoading(true);
    getCompetitorVideos()
      .then(setCompetitors)
      .catch(() => {})
      .finally(() => setCompetitorsLoading(false));
  }

  useEffect(() => {
    refreshAccount();
    refreshCompetitors();
  }, []);

  async function handleConnect() {
    setConnecting(true);
    setAccountError(null);
    try {
      const { authorize_url } = await getTikTokAuthorizeUrl();
      window.location.href = authorize_url;
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : "Chưa thể tạo link kết nối TikTok.");
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    if (!window.confirm("Ngắt kết nối tài khoản TikTok này?")) return;
    try {
      await disconnectTikTokAccount();
      refreshAccount();
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : "Không ngắt kết nối được.");
    }
  }

  async function handleSync() {
    setSyncing(true);
    setAccountError(null);
    try {
      await triggerTikTokSync();
      setTimeout(refreshAccount, 3000);
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : "Không đồng bộ được.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleAddCompetitorVideo() {
    if (!sourceUrl.trim() || submitting) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await createCompetitorVideo({
        source_url: sourceUrl.trim(),
        competitor_handle: handle.trim() || null,
        title_caption: titleCaption.trim() || null,
        duration_sec: durationSec.trim() ? Number(durationSec) : null,
        notes: notes.trim() || null,
      });
      setSourceUrl("");
      setHandle("");
      setTitleCaption("");
      setDurationSec("");
      setNotes("");
      refreshCompetitors();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Không thêm được video đối thủ.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAnalyze(id: number) {
    setAnalyzingId(id);
    setFormError(null);
    try {
      const updated = await analyzeCompetitorVideo(id);
      setCompetitors((prev) => prev.map((v) => (v.id === id ? updated : v)));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Phân tích thất bại.");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Xoá video đối thủ này?")) return;
    try {
      await deleteCompetitorVideo(id);
      setCompetitors((prev) => prev.filter((v) => v.id !== id));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Không xoá được.");
    }
  }

  return (
    <>
      <PageHeader
        title="Competitor Content Analyzer"
        subtitle="Kết nối tài khoản TikTok của bạn qua OAuth chính thức + phân tích pattern trừu tượng từ video đối thủ (nhập tay, không scrape). Cấu hình TikTok Client Key/Secret/Redirect URI ở trang Settings trước."
      />

      <section className="ci-section">
        <h2 className="ci-section-title">Tài khoản TikTok của bạn</h2>
        {accountError && <div className="ci-alert ci-alert-error">{accountError}</div>}
        {accountLoading ? (
          <div className="ci-loading">
            <Loader2 size={18} className="spin" />
          </div>
        ) : account ? (
          <div className="ci-account-card">
            <div className="ci-account-top">
              {account.avatar_url && <img src={account.avatar_url} alt="" className="ci-avatar" />}
              <div>
                <strong>{account.display_name ?? account.username ?? account.open_id}</strong>
                <div className="ci-account-sub">@{account.username ?? "—"}</div>
              </div>
              <div className="ci-account-actions">
                <button className="btn btn-secondary" onClick={handleSync} disabled={syncing}>
                  <RefreshCw size={14} className={syncing ? "spin" : ""} /> Sync now
                </button>
                <button className="btn btn-secondary" onClick={handleDisconnect}>
                  <Unlink size={14} /> Ngắt kết nối
                </button>
              </div>
            </div>
            <div className="ci-stats-row">
              <span>Followers: {num(account.follower_count)}</span>
              <span>Likes: {num(account.likes_count)}</span>
              <span>Videos: {num(account.video_count)}</span>
              <span>
                Đồng bộ gần nhất: {account.last_synced_at ? new Date(account.last_synced_at).toLocaleString("vi-VN") : "Chưa từng"}
              </span>
            </div>

            {videos.length > 0 && (
              <div className="ci-table-wrap">
                <table className="ci-table">
                  <thead>
                    <tr>
                      <th>Video</th>
                      <th>Views</th>
                      <th>Likes</th>
                      <th>Comments</th>
                      <th>Shares</th>
                      <th>Đăng lúc</th>
                    </tr>
                  </thead>
                  <tbody>
                    {videos.map((v) => (
                      <tr key={v.id}>
                        <td>{v.title || v.video_description || v.tiktok_video_id}</td>
                        <td>{num(v.view_count)}</td>
                        <td>{num(v.like_count)}</td>
                        <td>{num(v.comment_count)}</td>
                        <td>{num(v.share_count)}</td>
                        <td>{v.posted_at ? new Date(v.posted_at).toLocaleDateString("vi-VN") : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="ci-connect-card">
            <p>Chưa kết nối tài khoản TikTok nào.</p>
            <button className="btn btn-primary" onClick={handleConnect} disabled={connecting}>
              {connecting ? <Loader2 size={14} className="spin" /> : null} Connect TikTok
            </button>
            <p className="ci-hint">
              Cần cấu hình Client Key/Secret/Redirect URI ở <Link to="/settings">Settings</Link> trước.
            </p>
          </div>
        )}
      </section>

      <section className="ci-section">
        <h2 className="ci-section-title">Thêm video đối thủ để phân tích</h2>
        <p className="ci-hint">
          Dán URL video công khai của đối thủ và tự gõ lại những gì bạn đọc được công khai (caption, mô tả) -- hệ
          thống không tự động lấy dữ liệu số liệu/engagement của đối thủ (TikTok không cấp API chính thức cho việc
          này với app thương mại). AI chỉ trích xuất pattern trừu tượng, không sao chép script gốc.
        </p>
        {formError && <div className="ci-alert ci-alert-error">{formError}</div>}
        <div className="ci-form-grid">
          <input
            className="ci-input"
            placeholder="URL video TikTok của đối thủ *"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
          />
          <input className="ci-input" placeholder="@kênh đối thủ" value={handle} onChange={(e) => setHandle(e.target.value)} />
          <input
            className="ci-input"
            placeholder="Thời lượng (giây, nếu biết)"
            type="number"
            value={durationSec}
            onChange={(e) => setDurationSec(e.target.value)}
          />
          <input
            className="ci-input ci-input-wide"
            placeholder="Caption/tiêu đề công khai (tự điền qua oEmbed nếu để trống)"
            value={titleCaption}
            onChange={(e) => setTitleCaption(e.target.value)}
          />
          <textarea
            className="ci-input ci-input-wide"
            placeholder="Mô tả thêm những gì bạn xem được công khai (bối cảnh, twist, cảm xúc...)"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <button className="btn btn-primary" onClick={handleAddCompetitorVideo} disabled={!sourceUrl.trim() || submitting}>
          {submitting ? <Loader2 size={14} className="spin" /> : null} Thêm video
        </button>
      </section>

      <section className="ci-section">
        <h2 className="ci-section-title">Video đối thủ đã thêm</h2>
        {competitorsLoading ? (
          <div className="ci-loading">
            <Loader2 size={18} className="spin" />
          </div>
        ) : competitors.length === 0 ? (
          <EmptyState icon={Sparkles} title="Chưa có video đối thủ nào" description="Thêm một video ở form phía trên để bắt đầu." />
        ) : (
          <div className="ci-competitor-list">
            {competitors.map((c) => (
              <div key={c.id} className="ci-competitor-card">
                <div className="ci-competitor-top">
                  {c.thumbnail_url && <img src={c.thumbnail_url} alt="" className="ci-thumb" />}
                  <div className="ci-competitor-info">
                    <strong>{c.competitor_handle || c.author_name || "Không rõ kênh"}</strong>
                    <div className="ci-competitor-caption">{c.title_caption || "(chưa có caption)"}</div>
                  </div>
                  <div className="ci-competitor-actions">
                    {!c.analyzed_at && (
                      <button className="btn btn-secondary" onClick={() => handleAnalyze(c.id)} disabled={analyzingId === c.id}>
                        {analyzingId === c.id ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} Phân tích
                      </button>
                    )}
                    <button className="btn btn-secondary" onClick={() => handleDelete(c.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                {c.analyzed_at ? (
                  <div className="ci-pattern-grid">
                    {PATTERN_FIELDS.map((f) => (
                      <div key={f.key} className="ci-pattern-item">
                        <span className="ci-pattern-label">{f.label}</span>
                        <span className="ci-pattern-value">{String(c[f.key] ?? "—")}</span>
                      </div>
                    ))}
                    {c.reasoning && <p className="ci-reasoning">{c.reasoning}</p>}
                  </div>
                ) : (
                  <p className="ci-hint">Chưa phân tích.</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
