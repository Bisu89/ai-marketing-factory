import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clapperboard,
  ClipboardCheck,
  Loader2,
  RotateCcw,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { cancelBatch, generateBeatsForBatch, getBatch, renderBatch, retryBatch } from "../api/batch";
import { checkBatchQuality } from "../api/quality";
import { continueBatchProduction, produceBatch } from "../api/factory";
import type { Batch, BatchItem, BatchItemStatus } from "../types/batch";
import type { BatchQualitySummary } from "../types/quality";
import "./BatchDetailPage.css";

const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL: Record<BatchItemStatus, string> = {
  PENDING: "Pending",
  PROJECT_CREATED: "Project created",
  BEATS_READY: "Beats ready",
  READY_TO_RENDER: "Ready to render",
  NEEDS_REVIEW: "Needs review",
  RENDERING: "Rendering",
  COMPLETED: "Completed",
  FAILED: "Failed",
  SKIPPED: "Skipped",
  CANCELLED: "Cancelled",
};

const BATCH_STATUS_LABEL: Record<Batch["status"], string> = {
  DRAFT: "Draft",
  PROCESSING: "Processing",
  COMPLETED: "Completed",
  PARTIAL_FAILURE: "Partial failure",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

function isActive(batch: Batch): boolean {
  // Only real, observable states -- never a fabricated "in progress" guess.
  return batch.status === "PROCESSING" || batch.items.some((i) => i.status === "RENDERING");
}

export function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const id = Number(batchId);

  const [batch, setBatch] = useState<Batch | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Task 16 (see docs/features/42-content-quality-gate.md) -- a pure,
  // read-only dry run over the batch's current items; never fetched
  // automatically (it costs a real analysis pass per item), only on
  // request via the "Check Quality" button below.
  const [qualitySummary, setQualitySummary] = useState<BatchQualitySummary | null>(null);
  const [qualityChecking, setQualityChecking] = useState(false);
  const [qualityError, setQualityError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getBatch(id);
      setBatch(data);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load this batch.");
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (batch && isActive(batch)) {
      pollRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [batch, refresh]);

  async function runAction(name: string, action: () => Promise<Batch>) {
    setBusyAction(name);
    setActionError(null);
    try {
      const updated = await action();
      setBatch(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : `Could not ${name} this batch.`);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCheckQuality() {
    setQualityChecking(true);
    setQualityError(null);
    try {
      setQualitySummary(await checkBatchQuality(id));
    } catch (err) {
      setQualityError(err instanceof Error ? err.message : "Could not check batch quality.");
    } finally {
      setQualityChecking(false);
    }
  }

  // Task 18 -- see docs/features/44-one-click-factory-pipeline.md. Not a
  // second render trigger: produceBatch/continueBatchProduction call
  // FactoryPipeline.run_project() per eligible item, which itself only
  // ever creates a RenderJob through the same existing LocalRenderQueue
  // Render All (above) already uses -- this just adds Beat generation +
  // visual assignment + Quality Gate ahead of that, automatically.
  async function handleProduce() {
    setBusyAction("produce");
    setActionError(null);
    try {
      await produceBatch(id);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not produce this batch.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleContinueBatch() {
    setBusyAction("continue");
    setActionError(null);
    try {
      await continueBatchProduction(id);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not continue this batch.");
    } finally {
      setBusyAction(null);
    }
  }

  if (loadError && !batch) {
    return (
      <>
        <PageHeader title="Batch" actions={<BackLink navigate={navigate} />} />
        <div className="batch-alert batch-alert-error">{loadError}</div>
      </>
    );
  }

  if (!batch) {
    return (
      <>
        <PageHeader title="Batch" actions={<BackLink navigate={navigate} />} />
        <div className="bd-loading">
          <Loader2 size={18} className="spin" />
        </div>
      </>
    );
  }

  const pendingBeats = batch.items.filter((i) => i.status === "PROJECT_CREATED").length;
  const readyToRender = batch.items.filter((i) => i.status === "BEATS_READY").length;
  const retryable = batch.items.filter((i) => i.status === "FAILED" || i.status === "SKIPPED").length;
  const producible = batch.items.filter((i) =>
    ["PENDING", "PROJECT_CREATED", "BEATS_READY"].includes(i.status)
  ).length;
  const continuable = batch.items.filter((i) => i.status === "NEEDS_REVIEW" || i.status === "FAILED").length;
  const cancellable = batch.items.some((i) =>
    ["PENDING", "PROJECT_CREATED", "BEATS_READY", "RENDERING"].includes(i.status)
  );
  const completedCount = batch.items.filter((i) => i.status === "COMPLETED").length;

  return (
    <>
      <PageHeader
        title={batch.name}
        subtitle={`${BATCH_STATUS_LABEL[batch.status]} -- ${completedCount}/${batch.items.length} completed`}
        actions={<BackLink navigate={navigate} />}
      />

      {actionError && <div className="batch-alert batch-alert-error">{actionError}</div>}

      <div className="bd-actions">
        <button
          className="btn btn-primary"
          disabled={producible === 0 || busyAction != null}
          onClick={handleProduce}
        >
          {busyAction === "produce" ? <Loader2 size={14} className="spin" /> : <Wand2 size={14} />}
          Produce ({producible})
        </button>
        <button
          className="btn btn-secondary"
          disabled={continuable === 0 || busyAction != null}
          onClick={handleContinueBatch}
        >
          {busyAction === "continue" ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />}
          Continue Batch ({continuable})
        </button>
        <button
          className="btn btn-secondary"
          disabled={pendingBeats === 0 || busyAction != null}
          onClick={() => runAction("generate beats for", () => generateBeatsForBatch(id))}
        >
          {busyAction === "generate beats for" ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
          Generate Beats ({pendingBeats})
        </button>
        <button
          className="btn btn-primary"
          disabled={readyToRender === 0 || busyAction != null}
          onClick={() => runAction("render", () => renderBatch(id))}
        >
          {busyAction === "render" ? <Loader2 size={14} className="spin" /> : <Clapperboard size={14} />}
          Render All ({readyToRender})
        </button>
        <button
          className="btn btn-secondary"
          disabled={retryable === 0 || busyAction != null}
          onClick={() => runAction("retry", () => retryBatch(id))}
        >
          {busyAction === "retry" ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />}
          Retry Failed/Skipped ({retryable})
        </button>
        <button
          className="btn btn-secondary"
          disabled={!cancellable || busyAction != null}
          onClick={() => runAction("cancel", () => cancelBatch(id))}
        >
          {busyAction === "cancel" ? <Loader2 size={14} className="spin" /> : <Ban size={14} />}
          Cancel Batch
        </button>
        <button
          className="btn btn-secondary"
          disabled={readyToRender === 0 || qualityChecking}
          onClick={handleCheckQuality}
        >
          {qualityChecking ? <Loader2 size={14} className="spin" /> : <ClipboardCheck size={14} />}
          Check Quality
        </button>
      </div>

      {qualityError && <div className="batch-alert batch-alert-error">{qualityError}</div>}

      {qualitySummary && (
        <div className="bd-quality-summary">
          <h3>Batch Quality</h3>
          <p>{qualitySummary.items.length} project{qualitySummary.items.length === 1 ? "" : "s"} checked</p>
          <div className="bd-quality-counts">
            <span className="bd-quality-count bd-quality-count--ready">
              <CheckCircle2 size={13} /> READY {qualitySummary.ready}
            </span>
            <span className="bd-quality-count bd-quality-count--review">
              <AlertTriangle size={13} /> NEEDS_REVIEW {qualitySummary.needs_review}
            </span>
            <span className="bd-quality-count bd-quality-count--blocked">
              <XCircle size={13} /> BLOCKED {qualitySummary.blocked}
            </span>
          </div>
          <p className="bd-quality-hint">
            "Render All" above only enqueues the READY ones -- NEEDS_REVIEW/BLOCKED items are never rendered silently.
          </p>
        </div>
      )}

      <div className="bd-table-wrap">
        <table className="bd-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Script</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {batch.items.map((item) => (
              <ItemRow key={item.id} item={item} batchId={id} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function BackLink({ navigate }: { navigate: ReturnType<typeof useNavigate> }) {
  return (
    <button className="btn btn-secondary" onClick={() => navigate("/batches")}>
      <ArrowLeft size={14} />
      All Batches
    </button>
  );
}

function ItemRow({ item, batchId }: { item: BatchItem; batchId: number }) {
  return (
    <tr>
      <td>{item.index}</td>
      <td>
        <div className="bd-script-preview">{item.script_text.slice(0, 140)}</div>
        {item.error_message && <div className="bd-error-message">{item.error_message}</div>}
        {item.status === "BEATS_READY" && item.eligible === false && (
          <div className="bd-ineligible">
            <XCircle size={12} /> Not ready to render: {item.ineligible_reason}
          </div>
        )}
        {item.status === "BEATS_READY" && item.eligible === true && (
          <div className="bd-eligible">
            <CheckCircle2 size={12} /> Ready to render
          </div>
        )}
        {item.status === "BEATS_READY" && item.quality_status && item.quality_status !== "READY" && (
          <div className="bd-ineligible">
            <AlertTriangle size={12} /> Quality Gate: {item.quality_status} (score {item.quality_score})
          </div>
        )}
      </td>
      <td>
        <span className={`bd-status bd-status--${item.status}`}>{STATUS_LABEL[item.status]}</span>
      </td>
      <td>
        {item.project_id != null && (
          <Link className="btn btn-secondary bd-open-btn" to={`/video-factory?project=${item.project_id}&batch=${batchId}`}>
            Open Project
          </Link>
        )}
      </td>
    </tr>
  );
}
