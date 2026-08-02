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
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { getByPostType, getSummary, getTopPosts, getTrend, listUploads, uploadInsightCsv } from "../api/insights";
import type { InsightPost, InsightSummary, InsightUploadSummary, PostTypeBreakdown, TrendPoint } from "../types/insight";
import "./InsightsPage.css";

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

  async function refreshUploads(): Promise<InsightUploadSummary[]> {
    const list = await listUploads();
    setUploads(list);
    return list;
  }

  useEffect(() => {
    refreshUploads()
      .then((list) => {
        if (list.length > 0) setSelectedUploadId(list[0].id);
      })
      .catch(() => setError("Không tải được danh sách upload."));
    getTrend().then(setTrend).catch(() => undefined);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload thất bại.");
    } finally {
      setUploading(false);
    }
  }

  const trendPoints = (metric: "total_views" | "total_interactions") =>
    trend.map((t) => ({ label: new Date(t.uploaded_at).toLocaleDateString("vi-VN"), value: t[metric] }));

  return (
    <>
      <PageHeader
        title="Insights"
        subtitle="Upload file CSV 'Nội dung' xuất từ Meta Business Suite để phân tích hiệu suất bài đăng trên Page"
      />

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

      {error && <div className="insight-alert insight-alert-error">{error}</div>}
      {message && (
        <div className="insight-alert insight-alert-success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}

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
  );
}
