import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronRight,
  Clapperboard,
  ListChecks,
  Plus,
  RefreshCw,
  Wand2,
  XCircle,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { NewVideoModal } from "../components/NewVideoModal";
import { getDashboard } from "../api/dashboard";
import { cancelVideoComposeJob, retryVideoComposeJob } from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import type {
  AttentionPriority,
  DashboardAttentionItem,
  DashboardOut,
  DashboardVideo,
} from "../types/dashboard";
import "./DashboardPage.css";

const ACTIVE_POLL_MS = 3000;
const IDLE_POLL_MS = 15000;

function formatElapsed(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

function projectLink(projectId: number | null, batchId: number | null): string {
  if (projectId == null) return "/batches";
  return batchId != null
    ? `/video-factory?project=${projectId}&batch=${batchId}`
    : `/video-factory?project=${projectId}`;
}

const ATTENTION_ACTION_LABEL: Record<AttentionPriority, string> = {
  BLOCKED: "Fix",
  FAILED: "Details",
  NEEDS_REVIEW: "Review",
};

const ATTENTION_RANK: Record<AttentionPriority, number> = {
  BLOCKED: 0,
  FAILED: 1,
  NEEDS_REVIEW: 2,
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyJobId, setBusyJobId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [newVideoOpen, setNewVideoOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await getDashboard();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load production status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // 3s while something is actually rendering/queued, 15s otherwise -- no
  // push mechanism exists in this app (see docs/features/43), matching the
  // polling convention HistoryPage/BatchDetailPage already use.
  useEffect(() => {
    const active = data != null && (data.summary.rendering > 0 || data.queue.length > 0);
    pollRef.current = setTimeout(refresh, active ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [data, refresh]);

  async function handleCancel(jobId: number) {
    setBusyJobId(jobId);
    try {
      await cancelVideoComposeJob(jobId);
    } catch {
      // A stale/already-finished job -- the next refresh will show reality.
    } finally {
      setBusyJobId(null);
      refresh();
    }
  }

  async function handleRetry(jobId: number) {
    setBusyJobId(jobId);
    try {
      await retryVideoComposeJob(jobId);
    } catch {
      // Surfaced naturally: the failure stays in the alert list if retry couldn't start.
    } finally {
      setBusyJobId(null);
      refresh();
    }
  }

  const headerActions = (
    <div className="dash-header-actions">
      <button className="btn btn-secondary" onClick={() => setNewVideoOpen(true)}>
        <Plus size={14} /> New Video
      </button>
      <Link className="btn btn-primary" to="/batches?new=1">
        <Plus size={14} /> New Batch
      </Link>
    </div>
  );

  const newVideoModal = newVideoOpen && <NewVideoModal onClose={() => setNewVideoOpen(false)} />;

  if (loading) {
    return (
      <>
        <PageHeader title="Production Dashboard" actions={headerActions} />
        <div className="dash-loading">Loading production status...</div>
        {newVideoModal}
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Production Dashboard" actions={headerActions} />
        <div className="dash-alert dash-alert-error">
          Unable to load production status.
          <button className="btn btn-secondary" onClick={refresh}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
        {newVideoModal}
      </>
    );
  }

  if (!data) return null;

  if (!data.has_any_data) {
    return (
      <>
        <PageHeader title="Production Dashboard" actions={headerActions} />
        <EmptyState
          icon={Wand2}
          title="Welcome to Video Factory"
          description="No active production yet. Create your first video or batch to see it here."
        />
        {newVideoModal}
      </>
    );
  }

  const { summary, current_batch, current_render, queue, recent_videos, recent_failures } = data;
  const isIdle = !current_batch && !current_render && queue.length === 0;

  return (
    <>
      <PageHeader
        title="Production Dashboard"
        subtitle="What needs attention, what's running now, and what's finished."
        actions={headerActions}
      />

      {error && (
        <div className="dash-alert dash-alert-error">
          {error}
          <button className="btn btn-secondary" onClick={refresh}>
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      )}

      {/* -- 1. Numbers ---------------------------------------------------- */}
      <div className="dash-kpis">
        <KpiCard label="Ready" value={summary.ready} tone="ready" />
        <KpiCard label="Needs review" value={summary.needs_review} tone="review" />
        {summary.blocked > 0 && <KpiCard label="Blocked" value={summary.blocked} tone="blocked" />}
        <KpiCard label="Rendering" value={summary.rendering} tone="rendering" />
        <KpiCard label="Done today" value={summary.completed_today} tone="completed" />
      </div>

      {/* -- 2. Act now -------------------------------------------------- */}
      <AttentionPanel
        attention={data.attention}
        attentionTotal={data.attention_total}
        failures={recent_failures}
        busyJobId={busyJobId}
        onNavigate={(item) => navigate(projectLink(item.project_id, item.batch_id))}
        onRetry={handleRetry}
      />

      {/* -- 3. Running now -------------------------------------------------- */}
      <div className="dash-now">
        <section className="dash-card dash-card--now">
          <div className="dash-card-header">
            <h3>
              <Clapperboard size={15} /> Running now
            </h3>
            {current_batch && (
              <Link className="dash-header-link" to={`/batches/${current_batch.batch_id}`}>
                Open batch <ChevronRight size={13} />
              </Link>
            )}
          </div>

          {isIdle && <p className="dash-empty-note">Nothing in production right now.</p>}

          {current_batch && (
            <div className="dash-now-block">
              <div className="dash-batch-name">{current_batch.name}</div>
              <div className="dash-progress-track">
                <div
                  className="dash-progress-fill"
                  style={{
                    width: `${
                      current_batch.total > 0
                        ? (current_batch.completed / current_batch.total) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
              <div className="dash-progress-label">
                {current_batch.completed} / {current_batch.total} completed
              </div>
              <div className="dash-status-chips">
                {Object.entries(current_batch.status_counts).map(([status, count]) => (
                  <span key={status} className={`dash-chip dash-chip--${status}`}>
                    {count} {status.replace(/_/g, " ").toLowerCase()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {current_render && (
            <div className="dash-now-block dash-now-render">
              <div className="dash-render-grid">
                <Field label="Project" value={current_render.project_name} />
                <Field label="Phase" value={current_render.phase ?? "--"} />
                <Field
                  label="Beat"
                  value={
                    current_render.progress_current != null && current_render.progress_total != null
                      ? `${current_render.progress_current} / ${current_render.progress_total}`
                      : "--"
                  }
                />
                <Field label="Elapsed" value={formatElapsed(current_render.elapsed_seconds)} />
              </div>
              <div className="dash-card-actions">
                <Link
                  className="btn btn-secondary"
                  to={projectLink(current_render.project_id, current_render.batch_id)}
                >
                  View project
                </Link>
                <button
                  className="btn btn-secondary"
                  disabled={busyJobId === current_render.render_job_id}
                  onClick={() => handleCancel(current_render.render_job_id)}
                >
                  <Ban size={13} /> Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="dash-card dash-card--queue">
          <div className="dash-card-header">
            <h3>
              <ListChecks size={15} /> Render queue
              {queue.length > 0 && <span className="dash-count">{queue.length}</span>}
            </h3>
          </div>
          {queue.length === 0 ? (
            <p className="dash-empty-note">Queue is empty.</p>
          ) : (
            <ul className="dash-queue-list">
              {queue.map((entry) => (
                <li key={entry.render_job_id} className="dash-queue-item">
                  <span className={`dash-queue-status dash-queue-status--${entry.job_status}`}>
                    {entry.job_status}
                  </span>
                  <span className="dash-queue-title">{entry.title}</span>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={busyJobId === entry.render_job_id}
                    onClick={() => handleCancel(entry.render_job_id)}
                  >
                    <Ban size={13} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* -- 4. Finished -------------------------------------------------- */}
      <section className="dash-card">
        <div className="dash-card-header">
          <h3>
            <CheckCircle2 size={15} /> Recent videos
          </h3>
          <Link className="dash-header-link" to="/videos">
            All videos <ChevronRight size={13} />
          </Link>
        </div>
        {recent_videos.length === 0 ? (
          <p className="dash-empty-note">No completed renders yet.</p>
        ) : (
          <VideoList videos={recent_videos} />
        )}
      </section>

      {/* -- 5. At a glance -------------------------------------------------- */}
      <section className="dash-card dash-card--overview">
        <div className="dash-card-header">
          <h3>At a glance</h3>
        </div>
        <div className="dash-overview-grid">
          <div className="dash-overview-col">
            <span className="dash-overview-heading">Pipeline</span>
            {Object.keys(data.pipeline.status_counts).length === 0 ? (
              <p className="dash-empty-note">No batch items.</p>
            ) : (
              <ul className="dash-pipeline-list">
                {Object.entries(data.pipeline.status_counts).map(([status, count]) => (
                  <li key={status} className="dash-pipeline-row">
                    <span>{status.replace(/_/g, " ").toLowerCase()}</span>
                    <strong>{count}</strong>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="dash-overview-col">
            <span className="dash-overview-heading">Today</span>
            <ul className="dash-cost-list">
              <li>
                <span>Videos rendered</span>
                <strong>{data.cost.videos_rendered_today}</strong>
              </li>
              <li>
                <span>External API calls</span>
                <strong>{data.cost.external_video_api_calls}</strong>
              </li>
              <li>
                <span>External cost</span>
                <strong>${data.cost.external_video_api_cost.toFixed(2)}</strong>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {newVideoModal}
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="dash-field-label">{label}</div>
      <div className="dash-field-value">{value}</div>
    </div>
  );
}

function KpiCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`dash-kpi dash-kpi--${tone}${value > 0 ? " is-active" : ""}`}>
      <div className="dash-kpi-value">{value}</div>
      <div className="dash-kpi-label">{label}</div>
    </div>
  );
}

function AttentionPanel({
  attention,
  attentionTotal,
  failures,
  busyJobId,
  onNavigate,
  onRetry,
}: {
  attention: DashboardAttentionItem[];
  attentionTotal: number;
  failures: DashboardVideo[];
  busyJobId: number | null;
  onNavigate: (item: DashboardAttentionItem) => void;
  onRetry: (jobId: number) => void;
}) {
  const sorted = [...attention].sort(
    (a, b) => ATTENTION_RANK[a.priority] - ATTENTION_RANK[b.priority],
  );
  const totalCount = attentionTotal + failures.length;

  if (sorted.length === 0 && failures.length === 0) return null;

  return (
    <section className="dash-card dash-card--attention">
      <div className="dash-card-header">
        <h3>
          <AlertTriangle size={15} /> Needs attention
          <span className="dash-count dash-count--warn">{totalCount}</span>
        </h3>
        {attentionTotal > sorted.length && (
          <Link className="dash-header-link" to="/batches">
            View all <ChevronRight size={13} />
          </Link>
        )}
      </div>

      <ul className="dash-attention-list">
        {sorted.map((item) => (
          <li key={`a-${item.item_id}`} className="dash-attention-item">
            <span className={`dash-priority dash-priority--${item.priority}`}>
              {item.priority.replace("_", " ")}
            </span>
            <div className="dash-attention-body">
              <div className="dash-attention-project">{item.project_name}</div>
              <div className="dash-attention-reason">{item.reason}</div>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => onNavigate(item)}>
              {ATTENTION_ACTION_LABEL[item.priority]}
            </button>
          </li>
        ))}

        {failures.map((job) => (
          <li key={`f-${job.render_job_id}`} className="dash-attention-item">
            <span className="dash-priority dash-priority--FAILED">
              <XCircle size={11} /> Render failed
            </span>
            <div className="dash-attention-body">
              <div className="dash-attention-project">{job.title}</div>
              {job.error_message && <div className="dash-attention-reason">{job.error_message}</div>}
            </div>
            <button
              className="btn btn-secondary btn-sm"
              disabled={busyJobId === job.render_job_id}
              onClick={() => onRetry(job.render_job_id)}
            >
              Retry
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function VideoList({ videos }: { videos: DashboardVideo[] }) {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <ul className="dash-video-list">
      {videos.map((video) => (
        <li key={video.render_job_id} className="dash-video-item">
          <div className="dash-video-row">
            <CheckCircle2 size={15} className="dash-video-icon" />
            <span className="dash-video-title">{video.title}</span>
            <span className="dash-video-meta">
              {video.duration_sec != null ? `${video.duration_sec.toFixed(1)}s` : "--"}
            </span>
            <span className="dash-video-meta dash-video-meta--muted">
              {video.render_time_seconds != null
                ? `${video.render_time_seconds.toFixed(1)}s render`
                : "--"}
            </span>
            {video.output_media_url ? (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setOpenId(openId === video.render_job_id ? null : video.render_job_id)}
              >
                {openId === video.render_job_id ? "Hide" : "Preview"}
              </button>
            ) : (
              <span className="dash-video-meta">No preview</span>
            )}
          </div>
          {openId === video.render_job_id && video.output_media_url && (
            <video
              className="dash-video-preview"
              src={mediaUrl(video.output_media_url)}
              controls
              preload="metadata"
            />
          )}
        </li>
      ))}
    </ul>
  );
}
