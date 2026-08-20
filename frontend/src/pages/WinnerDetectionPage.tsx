import { useEffect, useState } from "react";
import { Loader2, TrendingUp, Trophy } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { BarRanking } from "../components/BarRanking";
import {
  getRisingFormats,
  getUnderperformingFormats,
  getWinnerFormats,
  getWinnerHooks,
  getWinnerPillars,
} from "../api/winnerDetection";
import type { TrendGroupStats, WinnerGroupStats } from "../types/winnerDetection";
import "./WinnerDetectionPage.css";

const DEFAULT_MIN_SAMPLE_SIZE = 5;

const CONFIDENCE_LABELS: Record<WinnerGroupStats["confidence"], string> = {
  insufficient: "Chưa đủ dữ liệu",
  low: "Độ tin cậy thấp",
  medium: "Độ tin cậy trung bình",
  high: "Độ tin cậy cao",
};

function pct(value: number | null): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function num(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("vi-VN");
}

function WinnerStatsTable({ groups }: { groups: WinnerGroupStats[] }) {
  if (groups.length === 0) {
    return <EmptyState icon={Trophy} title="Chưa có dữ liệu" description="Chưa có video nào gắn dữ liệu Insights cho nhóm này." />;
  }

  return (
    <>
      <BarRanking
        items={groups.filter((g) => g.performance_score != null).map((g) => ({ label: g.label, value: g.performance_score! }))}
        formatValue={(v) => v.toFixed(1)}
        emptyText="Chưa nhóm nào có đủ dữ liệu để tính điểm."
      />
      <div className="wd-table-wrap">
        <table className="wd-table">
          <thead>
            <tr>
              <th>Nhóm</th>
              <th>Mẫu (đã gắn/tổng)</th>
              <th>Độ tin cậy</th>
              <th>Views TB</th>
              <th>Views trung vị</th>
              <th>Engagement</th>
              <th>Share rate</th>
              <th>Điểm hiệu suất</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.label} className={g.meets_minimum_sample ? "" : "wd-row-insufficient"}>
                <td>
                  {g.label}
                  {g.note && <div className="wd-note">{g.note}</div>}
                </td>
                <td>
                  {g.linked_sample_size}/{g.sample_size}
                </td>
                <td>
                  <span className={`wd-confidence wd-confidence--${g.confidence}`}>{CONFIDENCE_LABELS[g.confidence]}</span>
                </td>
                <td>{num(g.avg_views)}</td>
                <td>{num(g.median_views)}</td>
                <td>{pct(g.avg_engagement_rate)}</td>
                <td>{pct(g.avg_share_rate)}</td>
                <td className="wd-score">{g.performance_score != null ? g.performance_score.toFixed(1) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TrendCards({ trends, icon: Icon }: { trends: TrendGroupStats[]; icon: typeof TrendingUp }) {
  if (trends.length === 0) {
    return <EmptyState icon={Icon} title="Chưa phát hiện xu hướng nào" description="Cần thêm dữ liệu trải dài theo thời gian để đánh giá xu hướng." />;
  }
  return (
    <div className="wd-trend-cards">
      {trends.map((t) => (
        <div key={t.label} className="wd-trend-card">
          <div className="wd-trend-card-top">
            <Icon size={16} className={t.trend === "rising" ? "wd-icon-rising" : "wd-icon-falling"} />
            <strong>{t.label}</strong>
            {t.change_pct != null && (
              <span className={t.trend === "rising" ? "wd-change-up" : "wd-change-down"}>
                {t.change_pct > 0 ? "+" : ""}
                {t.change_pct.toFixed(1)}%
              </span>
            )}
          </div>
          <p className="wd-trend-note">{t.note}</p>
        </div>
      ))}
    </div>
  );
}

export function WinnerDetectionPage() {
  const [minSampleSize, setMinSampleSize] = useState(DEFAULT_MIN_SAMPLE_SIZE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formats, setFormats] = useState<WinnerGroupStats[]>([]);
  const [hooks, setHooks] = useState<WinnerGroupStats[]>([]);
  const [pillars, setPillars] = useState<WinnerGroupStats[]>([]);
  const [rising, setRising] = useState<TrendGroupStats[]>([]);
  const [underperforming, setUnderperforming] = useState<WinnerGroupStats[]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      getWinnerFormats(minSampleSize),
      getWinnerHooks(minSampleSize),
      getWinnerPillars(minSampleSize),
      getRisingFormats(minSampleSize),
      getUnderperformingFormats(minSampleSize),
    ])
      .then(([f, h, p, r, u]) => {
        if (cancelled) return;
        setFormats(f);
        setHooks(h);
        setPillars(p);
        setRising(r);
        setUnderperforming(u);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Không tải được dữ liệu Winner Detection.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [minSampleSize]);

  return (
    <>
      <PageHeader
        title="Winner Detection"
        subtitle="Phát hiện pillar/format/hook nào thực sự hiệu quả hơn -- đã chuẩn hoá theo nền tảng, không xếp hạng theo view thô."
        actions={
          <label className="wd-threshold-field">
            <span>Mẫu tối thiểu để tính "winner"</span>
            <input
              type="number"
              min={1}
              value={minSampleSize}
              onChange={(e) => setMinSampleSize(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
        }
      />

      {error && <div className="wd-alert wd-alert-error">{error}</div>}

      {loading ? (
        <div className="wd-loading">
          <Loader2 size={20} className="spin" />
        </div>
      ) : (
        <>
          <section className="wd-section">
            <h2 className="wd-section-title">Top Formats</h2>
            <WinnerStatsTable groups={formats} />
          </section>

          <section className="wd-section">
            <h2 className="wd-section-title">Top Hooks</h2>
            <WinnerStatsTable groups={hooks} />
          </section>

          <section className="wd-section">
            <h2 className="wd-section-title">Top Pillars</h2>
            <WinnerStatsTable groups={pillars} />
          </section>

          <section className="wd-section">
            <h2 className="wd-section-title">Rising Formats</h2>
            <TrendCards trends={rising} icon={TrendingUp} />
          </section>

          <section className="wd-section">
            <h2 className="wd-section-title">Underperforming Formats</h2>
            <WinnerStatsTable groups={underperforming} />
          </section>
        </>
      )}
    </>
  );
}
