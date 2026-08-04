import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Upload,
  Loader2,
  CheckCircle2,
  BarChart3,
  Eye,
  Users,
  Heart,
  MessageCircle,
  Share2,
  Bookmark,
  Clock,
  FileText,
  Link2,
  Trophy,
  TrendingDown,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { BarRanking } from "../components/BarRanking";
import { getByPostType, getSummary, getTopPosts, getTrend, listUploads, uploadInsightCsv } from "../api/insights";
import {
  getLosers,
  getPerformanceOverview,
  getWinners,
  linkPublishLogToPost,
  listPublishLogs,
  listUnlinkedPosts,
} from "../api/publishLog";
import type { InsightPost, InsightSummary, InsightUploadSummary, PostTypeBreakdown, TrendPoint } from "../types/insight";
import type { PerformanceOverview, PublishLog, UnlinkedPost } from "../types/publishLog";
import "./InsightsPage.css";

type TabKey = "csv" | "performance";

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN");
}

function StatCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="insight-stat-card">
      <div className="insight-stat-card-icon">
        <Icon size={18} />
      </div>
      <div>
        <div className="insight-stat-card-value">{value}</div>
        <div className="insight-stat-card-label">{label}</div>
      </div>
    </div>
  );
}

interface TrendLineChartProps {
  title: string;
  points: { label: string; value: number }[];
}

function TrendLineChart({ title, points }: TrendLineChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const width = 320;
  const height = 120;
  const padding = 14;

  const maxValue = Math.max(...points.map((p) => p.value), 1);
  const stepX = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;
  const coords = points.map((p, i) => ({
    x: points.length > 1 ? padding + stepX * i : width / 2,
    y: height - padding - (p.value / maxValue) * (height - padding * 2),
  }));
  const pathD = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x},${c.y}`).join(" ");

  return (
    <div className="insight-chart">
      <div className="insight-chart-title">{title}</div>
      {points.length === 0 ? (
        <div className="insight-chart-empty">Chưa có dữ liệu</div>
      ) : (
        <div className="insight-chart-body">
          <svg viewBox={`0 0 ${width} ${height}`} className="insight-chart-svg">
            <line
              x1={padding}
              y1={height - padding}
              x2={width - padding}
              y2={height - padding}
              className="insight-chart-baseline"
            />
            {points.length > 1 && <path d={pathD} className="insight-chart-line" />}
            {coords.map((c, i) => (
              <circle
                key={i}
                cx={c.x}
                cy={c.y}
                r={4}
                className="insight-chart-dot"
                onMouseEnter={() => setHoverIndex(i)}
                onMouseLeave={() => setHoverIndex(null)}
              />
            ))}
          </svg>
          {hoverIndex !== null && (
            <div
              className="insight-chart-tooltip"
              style={{
                left: `${(coords[hoverIndex].x / width) * 100}%`,
                top: `${(coords[hoverIndex].y / height) * 100}%`,
              }}
            >
              <div>{points[hoverIndex].label}</div>
              <div>{formatNumber(points[hoverIndex].value)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function InsightsPage() {
  const [tab, setTab] = useState<TabKey>("csv");

  const [uploads, setUploads] = useState<InsightUploadSummary[]>([]);
  const [selectedUploadId, setSelectedUploadId] = useState<number | null>(null);
  const [summary, setSummary] = useState<InsightSummary | null>(null);
  const [posts, setPosts] = useState<InsightPost[]>([]);
  const [postTypes, setPostTypes] = useState<PostTypeBreakdown[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [sortBy, setSortBy] = useState<"views" | "interactions">("views");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [unlinkedPosts, setUnlinkedPosts] = useState<UnlinkedPost[]>([]);
  const [unlinkedLogs, setUnlinkedLogs] = useState<PublishLog[]>([]);
  const [linkingPostKey, setLinkingPostKey] = useState<string | null>(null);

  const [overview, setOverview] = useState<PerformanceOverview | null>(null);
  const [winners, setWinners] = useState<PublishLog[]>([]);
  const [losers, setLosers] = useState<PublishLog[]>([]);
  const [performanceLoaded, setPerformanceLoaded] = useState(false);

  async function refreshUploads(): Promise<InsightUploadSummary[]> {
    const list = await listUploads();
    setUploads(list);
    return list;
  }

  function refreshLinking() {
    listUnlinkedPosts().then(setUnlinkedPosts).catch(() => undefined);
    listPublishLogs()
      .then((logs) => setUnlinkedLogs(logs.filter((l) => !l.post_id)))
      .catch(() => undefined);
  }

  useEffect(() => {
    refreshUploads()
      .then((list) => {
        if (list.length > 0) setSelectedUploadId(list[0].id);
      })
      .catch(() => setError("Không tải được danh sách upload."));
    getTrend().then(setTrend).catch(() => undefined);
    refreshLinking();
  }, []);

  useEffect(() => {
    if (selectedUploadId === null) return;
    getSummary(selectedUploadId).then(setSummary).catch(() => setError("Không tải được số liệu tổng quan."));
    getByPostType(selectedUploadId).then(setPostTypes).catch(() => undefined);
  }, [selectedUploadId]);

  useEffect(() => {
    if (selectedUploadId === null) return;
    getTopPosts(selectedUploadId, sortBy, 20).then(setPosts).catch(() => undefined);
  }, [selectedUploadId, sortBy]);

  useEffect(() => {
    if (tab !== "performance" || performanceLoaded) return;
    setPerformanceLoaded(true);
    getPerformanceOverview().then(setOverview).catch(() => undefined);
    getWinners(10).then(setWinners).catch(() => undefined);
    getLosers(10).then(setLosers).catch(() => undefined);
  }, [tab, performanceLoaded]);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await uploadInsightCsv(file);
      const skippedNote = result.skipped_rows ? ` (bỏ qua ${result.skipped_rows} dòng lỗi)` : "";
      setMessage(`Đã upload ${result.row_count} bài đăng từ "${result.filename}".${skippedNote}`);
      await refreshUploads();
      setSelectedUploadId(result.id);
      getTrend().then(setTrend).catch(() => undefined);
      refreshLinking();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload thất bại.");
    } finally {
      setUploading(false);
    }
  }

  async function handleLink(post: UnlinkedPost, logId: number) {
    setLinkingPostKey(`${post.post_id}/${post.page_id}`);
    try {
      await linkPublishLogToPost(logId, post.post_id, post.page_id);
      refreshLinking();
      setPerformanceLoaded(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không gắn được bài viết này.");
    } finally {
      setLinkingPostKey(null);
    }
  }

  const trendPoints = (metric: "total_views" | "total_interactions") =>
    trend.map((t) => ({ label: new Date(t.uploaded_at).toLocaleDateString("vi-VN"), value: t[metric] }));

  return (
    <>
      <PageHeader
        title="Insights"
        subtitle="Phân tích hiệu suất bài đăng, và kết nối với dữ liệu video/AI Story trong Library"
      />

      <div className="insight-tabs">
        <button className={`btn ${tab === "csv" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("csv")}>
          Dữ liệu CSV
        </button>
        <button
          className={`btn ${tab === "performance" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setTab("performance")}
        >
          Performance Intelligence
        </button>
      </div>

      {error && <div className="insight-alert insight-alert-error">{error}</div>}
      {message && (
        <div className="insight-alert insight-alert-success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}

      {tab === "csv" && (
        <>
          <div className="insight-upload-row">
            <label className={`btn btn-primary insight-upload-btn${uploading ? " is-disabled" : ""}`}>
              {uploading ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
              Upload file CSV
              <input type="file" accept=".csv" onChange={handleFileChange} disabled={uploading} hidden />
            </label>

            {uploads.length > 0 && (
              <select
                className="insight-upload-select"
                value={selectedUploadId ?? ""}
                onChange={(e) => setSelectedUploadId(Number(e.target.value))}
              >
                {uploads.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.filename} — {new Date(u.uploaded_at).toLocaleString("vi-VN")} ({u.row_count} bài)
                  </option>
                ))}
              </select>
            )}
          </div>

          {uploads.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="Chưa có dữ liệu"
              description="Upload file CSV 'Nội dung' xuất từ Meta Business Suite để bắt đầu phân tích."
            />
          ) : (
            <>
              {summary && (
                <div className="insight-stat-grid">
                  <StatCard icon={Eye} label="Lượt xem" value={formatNumber(summary.total_views)} />
                  <StatCard icon={Users} label="Người xem" value={formatNumber(summary.total_viewers)} />
                  <StatCard icon={Heart} label="Lượt tương tác" value={formatNumber(summary.total_interactions)} />
                  <StatCard icon={MessageCircle} label="Bình luận" value={formatNumber(summary.total_comments)} />
                  <StatCard icon={Share2} label="Chia sẻ" value={formatNumber(summary.total_shares)} />
                  <StatCard icon={Bookmark} label="Lượt lưu" value={formatNumber(summary.total_saves)} />
                  <StatCard
                    icon={Clock}
                    label="Tỷ lệ giữ chân TB"
                    value={summary.avg_retention_pct != null ? `${summary.avg_retention_pct}%` : "—"}
                  />
                  <StatCard icon={FileText} label="Số bài đăng" value={String(summary.total_posts)} />
                </div>
              )}

              <div className="insight-chart-row">
                <TrendLineChart title="Lượt xem theo đợt" points={trendPoints("total_views")} />
                <TrendLineChart title="Lượt tương tác theo đợt" points={trendPoints("total_interactions")} />
              </div>

              {unlinkedPosts.length > 0 && (
                <div className="insight-section">
                  <div className="insight-section-header">
                    <h3>
                      <Link2 size={15} /> Bài chưa gắn video ({unlinkedPosts.length})
                    </h3>
                  </div>
                  <p className="insight-linking-hint">
                    Gắn các bài đăng dưới đây với video tương ứng trong Library (đã "Log Publish" ở
                    VideoDetailDrawer) để đưa vào Performance Intelligence.
                  </p>
                  <div className="insight-table-wrap">
                    <table className="insight-table">
                      <thead>
                        <tr>
                          <th>Bài đăng</th>
                          <th>Page</th>
                          <th>Lượt xem</th>
                          <th>Gắn với video</th>
                        </tr>
                      </thead>
                      <tbody>
                        {unlinkedPosts.map((post) => {
                          const key = `${post.post_id}/${post.page_id}`;
                          return (
                            <tr key={key}>
                              <td className="insight-table-title-cell">{post.title}</td>
                              <td>{post.page_name}</td>
                              <td>{formatNumber(post.views)}</td>
                              <td>
                                {unlinkedLogs.length === 0 ? (
                                  <span className="insight-linking-empty">Chưa có Publish Log nào để gắn</span>
                                ) : (
                                  <select
                                    disabled={linkingPostKey === key}
                                    defaultValue=""
                                    onChange={(e) => e.target.value && handleLink(post, Number(e.target.value))}
                                  >
                                    <option value="" disabled>
                                      Chọn video...
                                    </option>
                                    {unlinkedLogs.map((log) => (
                                      <option key={log.id} value={log.id}>
                                        {log.video_title} ({log.platform})
                                      </option>
                                    ))}
                                  </select>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="insight-section">
                <div className="insight-section-header">
                  <h3>Top bài đăng</h3>
                  <div className="insight-sort-toggle">
                    <button
                      className={`btn ${sortBy === "views" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setSortBy("views")}
                    >
                      Lượt xem
                    </button>
                    <button
                      className={`btn ${sortBy === "interactions" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setSortBy("interactions")}
                    >
                      Tương tác
                    </button>
                  </div>
                </div>
                <div className="insight-table-wrap">
                  <table className="insight-table">
                    <thead>
                      <tr>
                        <th>Bài đăng</th>
                        <th>Loại</th>
                        <th>Lượt xem</th>
                        <th>Tương tác</th>
                        <th>Giữ chân</th>
                      </tr>
                    </thead>
                    <tbody>
                      {posts.map((post) => (
                        <tr key={post.post_id}>
                          <td className="insight-table-title-cell">
                            {post.permalink ? (
                              <a href={post.permalink} target="_blank" rel="noreferrer">
                                {post.title}
                              </a>
                            ) : (
                              post.title
                            )}
                          </td>
                          <td>{post.post_type ?? "—"}</td>
                          <td>{formatNumber(post.views)}</td>
                          <td>{formatNumber(post.interactions)}</td>
                          <td>{post.retention_pct != null ? `${post.retention_pct}%` : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="insight-section">
                <h3>Theo loại bài viết</h3>
                <div className="insight-table-wrap">
                  <table className="insight-table">
                    <thead>
                      <tr>
                        <th>Loại bài viết</th>
                        <th>Số bài</th>
                        <th>Tổng lượt xem</th>
                        <th>Lượt xem TB</th>
                        <th>Giữ chân TB</th>
                      </tr>
                    </thead>
                    <tbody>
                      {postTypes.map((pt) => (
                        <tr key={pt.post_type}>
                          <td>{pt.post_type}</td>
                          <td>{pt.post_count}</td>
                          <td>{formatNumber(pt.total_views)}</td>
                          <td>{formatNumber(pt.avg_views)}</td>
                          <td>{pt.avg_retention_pct != null ? `${pt.avg_retention_pct}%` : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {tab === "performance" && (
        <>
          {!overview || (
            overview.by_topic.length === 0 &&
            overview.by_emotion.length === 0 &&
            overview.by_hook_type.length === 0 &&
            overview.by_story_style.length === 0
          ) ? (
            <EmptyState
              icon={Link2}
              title="Chưa có video nào được gắn với dữ liệu thật"
              description={'"Log Publish" cho video trong Library, rồi gắn với bài đăng đã upload ở tab "Dữ liệu CSV" để bắt đầu thấy insight thật.'}
            />
          ) : (
            <>
              <div className="insight-perf-grid">
                <div className="insight-section">
                  <h3>Top Topic (theo lượt xem thật)</h3>
                  <BarRanking items={overview.by_topic.map((b) => ({ label: b.label, value: b.total_views }))} />
                </div>
                <div className="insight-section">
                  <h3>Top Emotion</h3>
                  <BarRanking items={overview.by_emotion.map((b) => ({ label: b.label, value: b.total_views }))} />
                </div>
                <div className="insight-section">
                  <h3>Top Hook</h3>
                  <BarRanking items={overview.by_hook_type.map((b) => ({ label: b.label, value: b.total_views }))} />
                </div>
                <div className="insight-section">
                  <h3>Top Story Style</h3>
                  <BarRanking items={overview.by_story_style.map((b) => ({ label: b.label, value: b.total_views }))} />
                </div>
              </div>

              <div className="insight-perf-grid">
                <div className="insight-section">
                  <div className="insight-section-header">
                    <h3>
                      <Trophy size={15} /> Top 10 Winners
                    </h3>
                  </div>
                  <WinnerLoserTable rows={winners} />
                </div>
                <div className="insight-section">
                  <div className="insight-section-header">
                    <h3>
                      <TrendingDown size={15} /> Top 10 Losers
                    </h3>
                  </div>
                  <WinnerLoserTable rows={losers} />
                </div>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}

function WinnerLoserTable({ rows }: { rows: PublishLog[] }) {
  if (rows.length === 0) {
    return <p className="insight-linking-hint">Chưa có dữ liệu.</p>;
  }
  return (
    <div className="insight-table-wrap">
      <table className="insight-table">
        <thead>
          <tr>
            <th>Video</th>
            <th>Topic</th>
            <th>Hook</th>
            <th>Story</th>
            <th>Lượt xem</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="insight-table-title-cell">{row.video_title}</td>
              <td>{row.video_topic ?? "—"}</td>
              <td>{row.hook_type ?? "—"}</td>
              <td>{row.story_style ?? "—"}</td>
              <td>{formatNumber(row.views ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
