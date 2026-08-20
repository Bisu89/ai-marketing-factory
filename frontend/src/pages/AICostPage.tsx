import { useEffect, useState } from "react";
import { DollarSign, Loader2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { BarRanking } from "../components/BarRanking";
import { getAICostBatches, getAICostStories, getAICostSummary } from "../api/aiCost";
import type { AICostSummary, BatchCost, StoryCost } from "../types/aiCost";
import "./AICostPage.css";

function usd(value: number | null): string {
  return value == null ? "—" : `$${value.toFixed(value < 1 ? 4 : 2)}`;
}

export function AICostPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<AICostSummary | null>(null);
  const [stories, setStories] = useState<StoryCost[]>([]);
  const [batches, setBatches] = useState<BatchCost[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAICostSummary(), getAICostStories(), getAICostBatches()])
      .then(([s, st, b]) => {
        if (cancelled) return;
        setSummary(s);
        setStories(st);
        setBatches(b);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Không tải được dữ liệu chi phí AI.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasUnconfirmedPricing =
    summary != null && [...summary.by_provider, ...summary.by_model].some((g) => !g.all_confirmed && g.total_cost_usd > 0);

  return (
    <>
      <PageHeader
        title="AI Cost Tracking"
        subtitle="Chi phí AI thực tế cho Story/Hook/Caption/Scoring (theo token) và AI Image Generation (theo ảnh) -- không tính doanh thu."
      />

      {error && <div className="ac-alert ac-alert-error">{error}</div>}

      {loading ? (
        <div className="ac-loading">
          <Loader2 size={20} className="spin" />
        </div>
      ) : summary === null ? null : (
        <>
          {hasUnconfirmedPricing && (
            <div className="ac-alert ac-alert-warning">
              Một số giá dùng để tính chi phí là ước lượng tham khảo, chưa xác nhận với bảng giá thật của nhà cung cấp
              (xem app/modules/ai/pricing.py) -- số liệu bên dưới có thể lệch so với hoá đơn thật.
            </div>
          )}

          <div className="ac-kpis">
            <div className="ac-kpi">
              <div className="ac-kpi-value">{usd(summary.total_ai_cost_usd)}</div>
              <div className="ac-kpi-label">AI Cost (tổng)</div>
            </div>
            <div className="ac-kpi">
              <div className="ac-kpi-value">{summary.videos_generated.toLocaleString("vi-VN")}</div>
              <div className="ac-kpi-label">Videos Generated</div>
            </div>
            <div className="ac-kpi">
              <div className="ac-kpi-value">{usd(summary.average_cost_per_video_usd)}</div>
              <div className="ac-kpi-label">Average Cost / Video</div>
            </div>
            <div className="ac-kpi">
              <div className="ac-kpi-value">{usd(summary.cost_per_1000_videos_usd)}</div>
              <div className="ac-kpi-label">Cost / 1,000 Videos</div>
            </div>
          </div>
          <p className="ac-hint">{summary.average_cost_per_video_note}</p>

          <section className="ac-section">
            <h2 className="ac-section-title">Cost by Provider</h2>
            <BarRanking
              items={summary.by_provider.map((g) => ({ label: g.label, value: g.total_cost_usd }))}
              formatValue={(v) => usd(v)}
              emptyText="Chưa có lệnh gọi AI nào được ghi nhận."
            />
          </section>

          <section className="ac-section">
            <h2 className="ac-section-title">Cost by Model</h2>
            <BarRanking
              items={summary.by_model.map((g) => ({ label: g.label, value: g.total_cost_usd }))}
              formatValue={(v) => usd(v)}
              emptyText="Chưa có lệnh gọi AI nào được ghi nhận."
            />
          </section>

          <section className="ac-section">
            <h2 className="ac-section-title">Monthly AI Cost</h2>
            <BarRanking
              items={summary.by_month.map((g) => ({ label: g.label, value: g.total_cost_usd }))}
              formatValue={(v) => usd(v)}
              emptyText="Chưa có lệnh gọi AI nào được ghi nhận."
            />
          </section>

          <section className="ac-section">
            <h2 className="ac-section-title">Cost per Story</h2>
            {stories.length === 0 ? (
              <EmptyState icon={DollarSign} title="Chưa có Story nào" description="Chưa có StoryJob nào có lệnh gọi AI được ghi nhận." />
            ) : (
              <div className="ac-table-wrap">
                <table className="ac-table">
                  <thead>
                    <tr>
                      <th>Story Job</th>
                      <th>Video</th>
                      <th>Số lệnh gọi</th>
                      <th>Chi phí</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stories.map((s) => (
                      <tr key={s.story_job_id}>
                        <td>#{s.story_job_id}</td>
                        <td>#{s.video_id}</td>
                        <td>
                          {s.call_count}
                          {s.unpriced_call_count > 0 && <span className="ac-note"> ({s.unpriced_call_count} chưa tính được giá)</span>}
                        </td>
                        <td className="ac-cost-cell">{usd(s.total_cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="ac-section">
            <h2 className="ac-section-title">Cost per Batch</h2>
            {batches.length === 0 ? (
              <EmptyState icon={DollarSign} title="Chưa có Batch nào" description="Chưa có Content Batch nào chứa Story đã được tính giá." />
            ) : (
              <div className="ac-table-wrap">
                <table className="ac-table">
                  <thead>
                    <tr>
                      <th>Batch</th>
                      <th>Số Story</th>
                      <th>Chi phí</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batches.map((b) => (
                      <tr key={b.batch_id}>
                        <td>{b.batch_name}</td>
                        <td>{b.story_count}</td>
                        <td className="ac-cost-cell">{usd(b.total_cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
