import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Ban, CheckCircle2, Plus, RefreshCw, Wand2, XCircle } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { getDashboard } from "../api/dashboard";
import { cancelVideoComposeJob, retryVideoComposeJob } from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import type { AttentionPriority, DashboardOut, DashboardVideo } from "../types/dashboard";
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
  return batchId != null ? `/video-factory?project=${projectId}&batch=${batchId}` : `/video-factory?project=${projectId}`;
}

const ATTENTION_ACTION_LABEL: Record<AttentionPriority, string> = {
  BLOCKED: "Fix",
  FAILED: "Details",
  NEEDS_REVIEW: "Review",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyJobId, setBusyJobId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Section 25: 2-3s while something is actually rendering/queued, slower
  // otherwise -- no push mechanism exists in this app (no WebSocket/SSE
  // bridge from app.core.events.EventBus to the frontend, see
  // docs/features/43-production-dashboard.md), matching the same polling
  // convention already used by HistoryPage/BatchDetailPage.
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
      // Surfaced naturally: the failure stays in Recent Failures if retry couldn't start.
    } finally {
      setBusyJobId(null);
      refresh();
    }
  }

  const headerActions = (
    <div className="dash-header-actions">
      <Link className="btn btn-secondary" to="/video-factory">
        <Plus size={14} /> New Video
      </Link>
      <Link className="btn btn-primary" to="/batches?new=1">
        <Plus size={14} /> New Batch
      </Link>
    </div>
  );

  if (loading) {
    return (
      <>
        <PageHeader title="Production Dashboard" actions={headerActions} />
        <div className="dash-loading">Loading production status...</div>
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
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Production Dashboard"
        subtitle="What you're producing, what needs attention, what's rendering, what's finished."
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

      <div className="dash-kpis">
        <KpiCard label="Ready" value={data.summary.ready} tone="ready" />
        <KpiCard label="Needs Review" value={data.summary.needs_review} tone="review" />
        <KpiCard label="Rendering" value={data.summary.rendering} tone="rendering" />
        <KpiCard label="Completed Today" value={data.summary.completed_today} tone="completed" />
      </div>

      {data.current_batch && (
        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Current Production</h3>
            <Link className="btn btn-secondary" to={`/batches/${data.current_batch.batch_id}`}>
              Open Batch
            </Link>
          </div>
          <div className="dash-batch-name">{data.current_batch.name}</div>
          <div className="dash-progress-track">
            <div
              className="dash-progress-fill"
              style={{ width: `${data.current_batch.total > 0 ? (data.current_batch.completed / data.current_batch.total) * 100 : 0}%` }}
            />
          </div>
          <div className="dash-progress-label">
            {data.current_batch.completed} / {data.current_batch.total} completed
          </div>
          <div className="dash-status-chips">
            {Object.entries(data.current_batch.status_counts).map(([status, count]) => (
              <span key={status} className={`dash-chip dash-chip--${status}`}>
                {count} {status.replace(/_/g, " ").toLowerCase()}
              </span>
            ))}
          </div>
        </section>
      )}

      {data.current_render && (
        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Currently Rendering</h3>
          </div>
          <div className="dash-render-grid">
            <div>
              <div className="dash-field-label">Project</div>
              <div className="dash-field-value">{data.current_render.project_name}</div>
            </div>
            <div>
              <div className="dash-field-label">Phase</div>
              <div className="dash-field-value">{data.current_render.phase ?? "--"}</div>
            </div>
            <div>
              <div className="dash-field-label">Beat</div>
              <div className="dash-field-value">
                {data.current_render.progress_current != null && data.current_render.progress_total != null
                  ? `${data.current_render.progress_current} / ${data.current_render.progress_total}`
                  : "--"}
              </div>
            </div>
            <div>
              <div className="dash-field-label">Elapsed</div>
              <div className="dash-field-value">{formatElapsed(data.current_render.elapsed_seconds)}</div>
            </div>
          </div>
          <div className="dash-card-actions">
            <Link
              className="btn btn-secondary"
              to={projectLink(data.current_render.project_id, data.current_render.batch_id)}
            >
              View Project
            </Link>
            <button
              className="btn btn-secondary"
              disabled={busyJobId === data.current_render.render_job_id}
              onClick={() => handleCancel(data.current_render!.render_job_id)}
            >
              <Ban size={13} /> Cancel
            </button>
          </div>
        </section>
      )}

      <div className="dash-columns">
        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Needs Attention</h3>
          </div>
          {data.attention.length === 0 ? (
            <p className="dash-empty-note">Nothing needs attention right now.</p>
          ) : (
            <ul className="dash-attention-list">
              {data.attention.map((item) => (
                <li key={item.item_id} className="dash-attention-item">
                  <span className={`dash-priority dash-priority--${item.priority}`}>{item.priority.replace("_", " ")}</span>
                  <div className="dash-attention-body">
                    <div className="dash-attention-project">{item.project_name}</div>
                    <div className="dash-attention-reason">{item.reason}</div>
                  </div>
                  <button className="btn btn-secondary" onClick={() => navigate(projectLink(item.project_id, item.batch_id))}>
                    {ATTENTION_ACTION_LABEL[item.priority]}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data.attention_total > data.attention.length && (
            <Link className="dash-view-all" to="/batches">
              View All ({data.attention_total})
            </Link>
          )}
        </section>

        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Render Queue</h3>
          </div>
          {data.queue.length === 0 ? (
            <p className="dash-empty-note">No active jobs.</p>
          ) : (
            <ul className="dash-queue-list">
              {data.queue.map((entry) => (
                <li key={entry.render_job_id} className="dash-queue-item">
                  <span className={`dash-queue-status dash-queue-status--${entry.job_status}`}>{entry.job_status}</span>
                  <span className="dash-queue-title">{entry.title}</span>
                  <button
                    className="btn btn-secondary"
                    disabled={busyJobId === entry.render_job_id}
                    onClick={() => handleCancel(entry.render_job_id)}
                  >
                    <Ban size={13} /> Cancel
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="dash-card">
        <div className="dash-card-header">
          <h3>Recent Videos</h3>
        </div>
        {data.recent_videos.length === 0 ? (
          <p className="dash-empty-note">No completed renders yet.</p>
        ) : (
          <VideoList videos={data.recent_videos} />
        )}
      </section>

      {data.recent_failures.length > 0 && (
        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Recent Failures</h3>
          </div>
          <ul className="dash-failure-list">
            {data.recent_failures.map((job) => (
              <li key={job.render_job_id} className="dash-failure-item">
                <XCircle size={15} className="dash-failure-icon" />
                <div className="dash-failure-body">
                  <div className="dash-failure-title">{job.title}</div>
                  {job.error_message && <div className="dash-failure-message">{job.error_message}</div>}
                </div>
                <div className="dash-card-actions">
                  {job.project_id != null && (
                    <Link className="btn btn-secondary" to={projectLink(job.project_id, job.batch_id)}>
                      Details
                    </Link>
                  )}
                  <button
                    className="btn btn-secondary"
                    disabled={busyJobId === job.render_job_id}
                    onClick={() => handleRetry(job.render_job_id)}
                  >
                    Retry
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="dash-columns">
        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Production Pipeline</h3>
          </div>
          <ul className="dash-pipeline-list">
            {Object.entries(data.pipeline.status_counts).map(([status, count]) => (
              <li key={status} className="dash-pipeline-row">
                <span>{status.replace(/_/g, " ")}</span>
                <strong>{count}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className="dash-card">
          <div className="dash-card-header">
            <h3>Today's Rendering</h3>
          </div>
          <ul className="dash-cost-list">
            <li>
              <span>Videos rendered</span>
              <strong>{data.cost.videos_rendered_today}</strong>
            </li>
            <li>
              <span>External video-generation API calls</span>
              <strong>{data.cost.external_video_api_calls}</strong>
            </li>
            <li>
              <span>External video-generation cost</span>
              <strong>${data.cost.external_video_api_cost.toFixed(2)}</strong>
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}

function KpiCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`dash-kpi dash-kpi--${tone}`}>
      <div className="dash-kpi-value">{value}</div>
      <div className="dash-kpi-label">{label}</div>
    </div>
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
            <span className="dash-video-meta">{video.duration_sec != null ? `${video.duration_sec.toFixed(1)}s` : "--"}</span>
            <span className="dash-video-meta">
              {video.render_time_seconds != null ? `${video.render_time_seconds.toFixed(1)}s render` : "--"}
            </span>
            {video.output_media_url ? (
              <button
                className="btn btn-secondary"
                onClick={() => setOpenId(openId === video.render_job_id ? null : video.render_job_id)}
              >
                {openId === video.render_job_id ? "Hide" : "Preview"}
              </button>
            ) : (
              <span className="dash-video-meta">No preview</span>
            )}
          </div>
          {openId === video.render_job_id && video.output_media_url && (
            <video className="dash-video-preview" src={mediaUrl(video.output_media_url)} controls preload="metadata" />
          )}
        </li>
      ))}
    </ul>
  );
}
