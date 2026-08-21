import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { cancelFactoryRun, continueFactoryRun, getLatestFactoryRun, retryFactoryRun } from "../api/factory";
import { getProjectFinalQa } from "../api/finalQa";
import { checkProjectQuality } from "../api/quality";
import { PRODUCTION_STEPS, isActiveFactoryRun, stepIndexForStatus } from "../types/factory";
import type { FactoryRun } from "../types/factory";
import type { QAReport } from "../types/finalQa";
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
  const [qaReport, setQaReport] = useState<QAReport | null>(null);
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

  // Real user report: a render that finished while the browser tab was
  // backgrounded/inactive didn't show up until the page was manually
  // refreshed. Root cause -- browsers throttle setTimeout/setInterval in
  // inactive tabs (can slow to once a minute or less), so this timer-based
  // poll can sit stale for a long time; returning to the tab doesn't reset
  // it, it just waits for whatever's left of the throttled delay. An
  // immediate poll on tab-visible (document.visibilitychange, not window
  // focus -- fires reliably across browsers for the "switched back to this
  // tab" case) fixes it without changing the steady-state poll cadence.
  useEffect(() => {
    function handleVisibilityChange() {
      if (document.visibilityState === "visible") refresh();
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [refresh]);

  useEffect(() => {
    if (run?.render_job_id != null && handedOffJobId.current !== run.render_job_id) {
      handedOffJobId.current = run.render_job_id;
      onRenderJobReady(run.render_job_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.render_job_id]);

  useEffect(() => {
    // Task 28: a NEEDS_REVIEW caused by a post-render Final QA FAIL
    // (failed_stage === "FINAL_QA") has no pre-render QualityReport to show
    // -- that stage already passed, or this run wouldn't have a
    // render_job_id at all -- so it fetches the QAReport instead.
    if (run?.status === "NEEDS_REVIEW" && run.failed_stage === "FINAL_QA") {
      getProjectFinalQa(projectId).then((res) => setQaReport(res.report)).catch(() => setQaReport(null));
      setReport(null);
    } else if (run?.status === "NEEDS_REVIEW") {
      checkProjectQuality(projectId).then(setReport).catch(() => setReport(null));
      setQaReport(null);
    } else {
      setReport(null);
      setQaReport(null);
    }
  }, [run?.status, run?.failed_stage, projectId]);

  async function handleContinue(force = false) {
    if (run == null) return;
    setBusy(true);
    setActionError(null);
    try {
      setRun(await continueFactoryRun(run.id, force));
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
  // would just be a duplicate, staler view of the same thing. The one
  // exception (Task 28) is a post-render Final QA FAIL: that pause has no
  // display surface anywhere else (ReadyToPostCard only ever shows a
  // *complete* package, and Step 5's own render view has already finished
  // by the time FINAL_QA runs), so this component stays visible for it.
  const isQaReview = run.status === "NEEDS_REVIEW" && run.failed_stage === "FINAL_QA";
  if (run.render_job_id != null && !isQaReview) return null;

  if (isQaReview) {
    const failures = qaReport?.checks.filter((c) => c.status === "FAIL") ?? [];
    const warnings = qaReport?.checks.filter((c) => c.status === "WARN") ?? [];
    return (
      <div className="pp-card pp-card--review">
        <div className="pp-header">
          <AlertTriangle size={16} />
          <h3>Final QA Found a Problem</h3>
          {qaReport && <span className="pp-score">QA Score: {qaReport.score}/100</span>}
        </div>
        <p className="pp-subtitle">
          {run.review_reason_count} issue{run.review_reason_count === 1 ? "" : "s"} found in the finished package.
        </p>
        {(failures.length > 0 || warnings.length > 0) && (
          <ul className="pp-issue-list">
            {[...failures, ...warnings].map((check, i) => (
              <li key={i} className={`pp-issue pp-issue--${check.severity}`}>
                {check.message}
                {check.repair_stage && check.repair_stage !== "UNKNOWN" && (
                  <span className="pp-issue-repair"> (fix: {check.repair_stage})</span>
                )}
              </li>
            ))}
          </ul>
        )}
        {actionError && <div className="pp-alert">{actionError}</div>}
        <div className="pp-actions">
          <button className="btn btn-primary" disabled={busy} onClick={() => handleContinue(false)}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Re-check Final QA
          </button>
        </div>
      </div>
    );
  }

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
          <button className="btn btn-primary" disabled={busy} onClick={() => handleContinue(false)}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Continue Production
          </button>
          {/* Real bug report: "Continue Production" re-runs the Quality
              Gate from scratch, so a still-true warning (nothing about the
              BeatPlan changed) re-pauses the run every time -- an
              unescapable loop with no way to actually proceed short of
              editing the beat plan. This button skips re-checking and
              renders anyway, matching evaluate_readiness's own documented
              (but previously unimplemented) "NEEDS_REVIEW is override-able"
              intent -- never shown for a BLOCKED-severity result, since
              report.issues (errors) only exist for that classification, not
              a NEEDS_REVIEW pause like this one. */}
          <button className="btn btn-secondary" disabled={busy} onClick={() => handleContinue(true)}>
            Continue Anyway
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
