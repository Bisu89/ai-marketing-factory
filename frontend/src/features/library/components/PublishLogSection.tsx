import { useEffect, useState } from "react";
import { Eye, Heart, Plus, Trash2 } from "lucide-react";
import { createPublishLog, deletePublishLog, listPublishLogs } from "../../../api/publishLog";
import { listStoryJobs } from "../../../api/story";
import { STORY_STYLE_LABELS, type StoryJob, type StoryStyle } from "../../../types/story";
import { PUBLISH_LOG_STATUS_LABELS, type PublishLog, type PublishLogStatus } from "../../../types/publishLog";
import "./PublishLogSection.css";

const STORY_STYLES = Object.keys(STORY_STYLE_LABELS) as StoryStyle[];

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN");
}

interface PublishLogSectionProps {
  videoId: number;
}

export function PublishLogSection({ videoId }: PublishLogSectionProps) {
  const [logs, setLogs] = useState<PublishLog[]>([]);
  const [storyJobs, setStoryJobs] = useState<StoryJob[]>([]);
  const [hookSuggestions, setHookSuggestions] = useState<string[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pageName, setPageName] = useState("");
  const [hookType, setHookType] = useState("");
  const [storyStyle, setStoryStyle] = useState<StoryStyle | "">("");
  const [selectedStoryVersionId, setSelectedStoryVersionId] = useState<number | "">("");
  const [affiliateProduct, setAffiliateProduct] = useState("");
  const [affiliateClicks, setAffiliateClicks] = useState(0);
  const [affiliateSales, setAffiliateSales] = useState(0);
  const [affiliateRevenue, setAffiliateRevenue] = useState(0);
  const [status, setStatus] = useState<PublishLogStatus>("none");
  const [submitting, setSubmitting] = useState(false);

  function loadLogs() {
    listPublishLogs(videoId).then(setLogs).catch(() => setError("Không tải được lịch sử đăng bài."));
  }

  useEffect(() => {
    loadLogs();
    listStoryJobs(videoId).then(setStoryJobs).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  function openForm() {
    setShowForm((v) => !v);
    // Loaded lazily, only when the form is first opened -- distinct hook
    // names typed across every past publish log, so the same wording gets
    // reused consistently instead of near-duplicate variants piling up.
    if (hookSuggestions.length === 0) {
      listPublishLogs()
        .then((all) => {
          const distinct = Array.from(new Set(all.map((l) => l.hook_type).filter((h): h is string => !!h)));
          setHookSuggestions(distinct);
        })
        .catch(() => undefined);
    }
  }

  function handlePickStoryVersion(versionId: number | "") {
    setSelectedStoryVersionId(versionId);
    if (versionId === "") return;
    const job = storyJobs.find((j) => j.versions.some((v) => v.id === versionId));
    if (job) setStoryStyle(job.style);
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await createPublishLog({
        video_id: videoId,
        page_name: pageName.trim() || undefined,
        hook_type: hookType.trim() || undefined,
        story_style: storyStyle || undefined,
        ai_story_job_id: selectedStoryVersionId
          ? storyJobs.find((j) => j.versions.some((v) => v.id === selectedStoryVersionId))?.id
          : undefined,
        affiliate_product: affiliateProduct.trim() || undefined,
        affiliate_clicks: affiliateClicks,
        affiliate_sales: affiliateSales,
        affiliate_revenue: affiliateRevenue,
        status,
      });
      setShowForm(false);
      setPageName("");
      setHookType("");
      setStoryStyle("");
      setSelectedStoryVersionId("");
      setAffiliateProduct("");
      setAffiliateClicks(0);
      setAffiliateSales(0);
      setAffiliateRevenue(0);
      setStatus("none");
      loadLogs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được lượt đăng bài.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(logId: number) {
    try {
      await deletePublishLog(logId);
      loadLogs();
    } catch {
      // Ignore transient failure; user can retry the click.
    }
  }

  const allStoryVersions = storyJobs.flatMap((job) =>
    job.versions.map((v) => ({ id: v.id, title: v.title, jobStyle: job.style })),
  );

  return (
    <div className="publish-log-section">
      <div className="drawer-row-label publish-log-header">
        <span>Hiệu suất đăng bài</span>
        <button className="btn btn-secondary publish-log-add-btn" onClick={openForm}>
          <Plus size={13} />
          Log Publish
        </button>
      </div>

      {error && <div className="publish-log-error">{error}</div>}

      {logs.length === 0 && !showForm && <p className="publish-log-empty">Video này chưa được ghi nhận đăng bài.</p>}

      {logs.length > 0 && (
        <div className="publish-log-list">
          {logs.map((log) => (
            <div key={log.id} className="publish-log-card">
              <div className="publish-log-card-top">
                <span className="publish-log-platform">{log.platform}</span>
                <span className="publish-log-date">{new Date(log.published_at).toLocaleDateString("vi-VN")}</span>
                <button className="publish-log-delete" onClick={() => handleDelete(log.id)} aria-label="Xoá">
                  <Trash2 size={12} />
                </button>
              </div>
              <div className="publish-log-card-meta">
                {log.hook_type && <span>Hook: {log.hook_type}</span>}
                {log.story_style && <span>Story: {STORY_STYLE_LABELS[log.story_style as StoryStyle] ?? log.story_style}</span>}
                <span>{PUBLISH_LOG_STATUS_LABELS[log.status]}</span>
              </div>
              {log.post_id ? (
                <div className="publish-log-stats">
                  <span>
                    <Eye size={12} /> {formatNumber(log.views ?? 0)}
                  </span>
                  <span>
                    <Heart size={12} /> {formatNumber(log.interactions ?? 0)}
                  </span>
                </div>
              ) : (
                <div className="publish-log-unlinked">Chưa gắn với dữ liệu Insights</div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="publish-log-form">
          <label>
            Tên Page
            <input value={pageName} onChange={(e) => setPageName(e.target.value)} placeholder="VD: My Fanpage" />
          </label>

          <label>
            Hook
            <input
              value={hookType}
              onChange={(e) => setHookType(e.target.value)}
              placeholder="VD: Beard + Surprise"
              list="hook-type-suggestions"
            />
          </label>

          {allStoryVersions.length > 0 && (
            <label>
              Phiên bản AI Story đã dùng (tuỳ chọn)
              <select
                value={selectedStoryVersionId}
                onChange={(e) => handlePickStoryVersion(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Không dùng AI Story / tự viết</option>
                {allStoryVersions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title} ({STORY_STYLE_LABELS[v.jobStyle]})
                  </option>
                ))}
              </select>
            </label>
          )}

          <label>
            Story style
            <select value={storyStyle} onChange={(e) => setStoryStyle(e.target.value as StoryStyle)}>
              <option value="">— Chọn —</option>
              {STORY_STYLES.map((s) => (
                <option key={s} value={s}>
                  {STORY_STYLE_LABELS[s]}
                </option>
              ))}
            </select>
          </label>

          <div className="publish-log-affiliate-row">
            <label>
              Sản phẩm affiliate
              <input value={affiliateProduct} onChange={(e) => setAffiliateProduct(e.target.value)} />
            </label>
            <label>
              Clicks
              <input type="number" min={0} value={affiliateClicks} onChange={(e) => setAffiliateClicks(Number(e.target.value))} />
            </label>
            <label>
              Đơn hàng
              <input type="number" min={0} value={affiliateSales} onChange={(e) => setAffiliateSales(Number(e.target.value))} />
            </label>
            <label>
              Doanh thu
              <input type="number" min={0} value={affiliateRevenue} onChange={(e) => setAffiliateRevenue(Number(e.target.value))} />
            </label>
          </div>

          <label>
            Trạng thái
            <select value={status} onChange={(e) => setStatus(e.target.value as PublishLogStatus)}>
              {(Object.keys(PUBLISH_LOG_STATUS_LABELS) as PublishLogStatus[]).map((s) => (
                <option key={s} value={s}>
                  {PUBLISH_LOG_STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </label>

          <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
            Lưu
          </button>

          <datalist id="hook-type-suggestions">
            {hookSuggestions.map((h) => (
              <option key={h} value={h} />
            ))}
          </datalist>
        </div>
      )}
    </div>
  );
}
