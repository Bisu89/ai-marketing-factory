import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { cancelFactoryRun, continueFactoryRun, getLatestFactoryRun, retryFactoryRun } from "../api/factory";
import { checkProjectQuality } from "../api/quality";
import { PRODUCTION_STEPS, isActiveFactoryRun, stepIndexForStatus } from "../types/factory";
import type { FactoryRun } from "../types/factory";
import type { QualityReport } from "../types/quality";
import "./ProductionProgress.css";

const ACTIVE_POLL_MS = 1500;

interface ProductionProgressProps {
  projectId: number;
  // Called once this run has a real RenderJob to show -- the parent hands
  // off entirely to VideoFactoryPage's own existing job-polling/Step-5 UI
  // from that point on (see docs/features/44-one-click-factory-pipeline.md
  // -- this component never re-implements render-status display).
  onRenderJobReady: (jobId: number) => void;
  onReviewBeat?: (beatId: string) => void;
}

// Task 18's "Production" checklist (section 26) -- shown above the manual
// step wizard whenever a FactoryRun exists for the loaded project. Purely
// a convenience layer: the existing Beat/Visual/Render steps underneath
// are untouched and still fully usable on their own.
export function ProductionProgress({ projectId, onRenderJobReady, onReviewBeat }: ProductionProgressProps) {
  const [run, setRun] = useState<FactoryRun | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [report, setReport] = useState<QualityReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handedOffJobId = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const latest = await getLatestFactoryRun(projectId);
      setRun(latest);
    } catch {
      // A project with no run yet (or a transient fetch error) simply
      // shows nothing -- this component is a convenience overlay, not
      // load-bearing for the page underneath it.
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (run != null && isActiveFactoryRun(run.status)) {
      pollRef.current = setTimeout(refresh, ACTIVE_POLL_MS);
    }
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [run, refresh]);

  useEffect(() => {
    if (run?.render_job_id != null && handedOffJobId.current !== run.render_job_id) {
      handedOffJobId.current = run.render_job_id;
      onRenderJobReady(run.render_job_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.render_job_id]);

  useEffect(() => {
    if (run?.status === "NEEDS_REVIEW") {
      checkProjectQuality(projectId).then(setReport).catch(() => setReport(null));
    } else {
      setReport(null);
    }
  }, [run?.status, projectId]);

  async function handleContinue() {
    if (run == null) return;
    setBusy(true);
    setActionError(null);
    try {
      setRun(await continueFactoryRun(run.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not continue production.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry() {
    if (run == null) return;
    setBusy(true);
    setActionError(null);
    try {
      setRun(await retryFactoryRun(run.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not retry production.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (run == null) return;
    setBusy(true);
    setActionError(null);
    try {
      setRun(await cancelFactoryRun(run.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not cancel production.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded || run == null) return null;
  // Once a RenderJob exists, VideoFactoryPage's own Step 5 already shows
  // full render status/progress/preview -- showing it a second time here
  // would just be a duplicate, staler view of the same thing.
  if (run.render_job_id != null) return null;

  if (run.status === "NEEDS_REVIEW") {
    return (
      <div className="pp-card pp-card--review">
        <div className="pp-header">
          <AlertTriangle size={16} />
          <h3>Production Paused</h3>
          {report && (
            <span className="pp-score">
              Quality Score: {report.score}/100
            </span>
          )}
        </div>
        <p className="pp-subtitle">
          {run.review_reason_count} issue{run.review_reason_count === 1 ? "" : "s"} require your attention.
        </p>
        {report && (report.issues.length > 0 || report.warnings.length > 0) && (
          <ul className="pp-issue-list">
            {[...report.issues, ...report.warnings].map((issue, i) => (
              <li key={i} className={`pp-issue pp-issue--${issue.severity}`}>
                <button
                  className="pp-issue-link"
                  onClick={() => issue.beat_id && onReviewBeat?.(issue.beat_id)}
                  disabled={!issue.beat_id}
                >
                  {issue.message}
                </button>
              </li>
            ))}
          </ul>
        )}
        {actionError && <div className="pp-alert">{actionError}</div>}
        <div className="pp-actions">
          <button className="btn btn-primary" disabled={busy} onClick={handleContinue}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Continue Production
          </button>
        </div>
      </div>
    );
  }

  if (run.status === "FAILED") {
    return (
      <div className="pp-card pp-card--failed">
        <div className="pp-header">
          <XCircle size={16} />
          <h3>Production Failed</h3>
        </div>
        <div className="pp-fail-grid">
          <div>
            <div className="pp-field-label">Stage</div>
            <div className="pp-field-value">{run.failed_stage ?? "--"}</div>
          </div>
          <div>
            <div className="pp-field-label">Reason</div>
            <div className="pp-field-value">{run.error_message ?? "An unexpected error occurred."}</div>
          </div>
        </div>
        {actionError && <div className="pp-alert">{actionError}</div>}
        <div className="pp-actions">
          <button className="btn btn-primary" disabled={busy} onClick={handleRetry}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (run.status === "CANCELLED") {
    return (
      <div className="pp-card">
        <div className="pp-header">
          <Ban size={16} />
          <h3>Production Cancelled</h3>
        </div>
        <p className="pp-subtitle">The project itself is untouched -- edit it below, or start again.</p>
      </div>
    );
  }

  if (run.status === "READY_TO_RENDER") {
    // render_after_quality_pass=false in this project's factory config --
    // the pipeline deliberately stopped short of creating a RenderJob.
    // FactoryPipeline never invokes the renderer itself in this case; the
    // existing Render step below (Step 5) is the one real render trigger.
    return (
      <div className="pp-card">
        <div className="pp-header">
          <CheckCircle2 size={16} />
          <h3>Ready to Render</h3>
        </div>
        <p className="pp-subtitle">
          Quality Score: {run.quality_score ?? "--"}/100. Automatic rendering is off for this project -- use the
          Render step below when you're ready.
        </p>
      </div>
    );
  }

  // Active local stages (PREPARING..QUALITY_CHECK).
  const currentStepIndex = stepIndexForStatus(run.status);
  return (
    <div className="pp-card">
      <div className="pp-header">
        <Loader2 size={16} className="spin" />
        <h3>Production</h3>
      </div>
      <ul className="pp-checklist">
        {PRODUCTION_STEPS.map((label, index) => (
          <li key={label} className="pp-checklist-item">
            {index < currentStepIndex ? (
              <CheckCircle2 size={15} className="pp-step-done" />
            ) : index === currentStepIndex ? (
              <Loader2 size={15} className="spin pp-step-active" />
            ) : (
              <Circle size={15} className="pp-step-pending" />
            )}
            <span className={index === currentStepIndex ? "pp-step-label pp-step-label--active" : "pp-step-label"}>
              {label}
            </span>
          </li>
        ))}
      </ul>
      {actionError && <div className="pp-alert">{actionError}</div>}
      <div className="pp-actions">
        <button className="btn btn-secondary" disabled={busy} onClick={handleCancel}>
          {busy ? <Loader2 size={14} className="spin" /> : <Ban size={13} />}
          Cancel
        </button>
      </div>
    </div>
  );
}
