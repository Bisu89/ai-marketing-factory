import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Ban, Loader2, RotateCcw } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { cancelContentBatch, getContentBatch, retryContentBatchItem, runContentBatch } from "../api/contentBatch";
import type { ContentBatch, ContentBatchItem, ContentBatchItemStatus } from "../types/contentBatch";
import "./ContentBatchDetailPage.css";

const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL: Record<ContentBatchItemStatus, string> = {
  PENDING: "Chờ xử lý",
  GENERATING: "Đang sinh truyện...",
  COMPLETED: "Đã sinh, chờ chấm điểm",
  SCORED: "Đã chấm điểm",
  APPROVED: "Đạt",
  REJECTED: "Không đạt",
  FAILED: "Lỗi",
  CANCELLED: "Đã huỷ",
};

const BATCH_STATUS_LABEL: Record<ContentBatch["status"], string> = {
  DRAFT: "Nháp",
  PROCESSING: "Đang xử lý",
  COMPLETED: "Hoàn tất",
  PARTIAL_FAILURE: "Một phần lỗi",
  FAILED: "Lỗi",
  CANCELLED: "Đã huỷ",
};

function isActive(batch: ContentBatch): boolean {
  return batch.status === "PROCESSING" || batch.items.some((i) => i.status === "GENERATING" || i.status === "PENDING");
}

function summarize(batch: ContentBatch) {
  const total = batch.items.length;
  const done = batch.items.filter((i) => i.status === "APPROVED" || i.status === "REJECTED").length;
  const failed = batch.items.filter((i) => i.status === "FAILED").length;
  const approved = batch.items.filter((i) => i.status === "APPROVED").length;
  return { total, done, failed, approved };
}

function ItemRow({ item, onRetry, retrying }: { item: ContentBatchItem; onRetry: () => void; retrying: boolean }) {
  return (
    <tr>
      <td>#{item.index}</td>
      <td>Ý tưởng #{item.idea_id}</td>
      <td>
        <span className={`cbd-status cbd-status--${item.status}`}>{STATUS_LABEL[item.status]}</span>
        {item.error_message && <div className="cbd-item-error">{item.error_message}</div>}
      </td>
      <td>{item.quality_score != null ? `${item.quality_score.toFixed(1)} / 90` : "—"}</td>
      <td>
        {item.status === "FAILED" && (
          <button className="btn btn-secondary cbd-retry-btn" onClick={onRetry} disabled={retrying}>
            {retrying ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />}
            Thử lại
          </button>
        )}
      </td>
    </tr>
  );
}

export function ContentBatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();
  const id = Number(batchId);

  const [batch, setBatch] = useState<ContentBatch | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [retryingItemId, setRetryingItemId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getContentBatch(id);
      setBatch(data);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Không tải được batch này.");
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

  async function handleRun() {
    setBusyAction("run");
    setActionError(null);
    try {
      setBatch(await runContentBatch(id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Không chạy được batch.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCancel() {
    setBusyAction("cancel");
    setActionError(null);
    try {
      setBatch(await cancelContentBatch(id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Không huỷ được batch.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleRetryItem(itemId: number) {
    setRetryingItemId(itemId);
    setActionError(null);
    try {
      setBatch(await retryContentBatchItem(id, itemId));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Không thử lại được mục này.");
    } finally {
      setRetryingItemId(null);
    }
  }

  if (loadError && !batch) {
    return (
      <div className="cbd-alert cbd-alert-error">
        <AlertTriangle size={16} />
        {loadError}
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="cbd-loading">
        <Loader2 size={20} className="spin" />
      </div>
    );
  }

  const summary = summarize(batch);
  const hasPending = batch.items.some((i) => i.status === "PENDING");
  const hasFailed = batch.items.some((i) => i.status === "FAILED");

  return (
    <>
      <PageHeader
        title={batch.name}
        subtitle={`Video #${batch.video_id} · style "${batch.style}" · ngưỡng ${batch.score_threshold.toFixed(1)}/10`}
        actions={
          <button className="btn btn-secondary" onClick={() => navigate("/content-batches")}>
            <ArrowLeft size={14} />
            Quay lại
          </button>
        }
      />

      <div className="cbd-summary-bar">
        <span className={`cbd-batch-status cbd-batch-status--${batch.status}`}>{BATCH_STATUS_LABEL[batch.status]}</span>
        <span>
          {summary.done}/{summary.total} đã xử lý · {summary.approved} đạt · {summary.failed} lỗi
        </span>
        <div className="cbd-actions">
          {hasPending && (
            <button className="btn btn-primary" onClick={handleRun} disabled={busyAction === "run"}>
              {busyAction === "run" ? <Loader2 size={14} className="spin" /> : null}
              Chạy batch
            </button>
          )}
          {hasPending && (
            <button className="btn btn-secondary" onClick={handleCancel} disabled={busyAction === "cancel"}>
              {busyAction === "cancel" ? <Loader2 size={14} className="spin" /> : <Ban size={14} />}
              Huỷ các mục đang chờ
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="cbd-alert cbd-alert-error">
          <AlertTriangle size={14} />
          {actionError}
        </div>
      )}
      {hasFailed && (
        <p className="cbd-hint">
          Các mục lỗi không bị xoá — bạn có thể xem lý do lỗi và bấm "Thử lại" cho từng mục.
        </p>
      )}

      <div className="cbd-table-wrap">
        <table className="cbd-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Ý tưởng</th>
              <th>Trạng thái</th>
              <th>Điểm</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {batch.items.map((item) => (
              <ItemRow
                key={item.id}
                item={item}
                onRetry={() => handleRetryItem(item.id)}
                retrying={retryingItemId === item.id}
              />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
