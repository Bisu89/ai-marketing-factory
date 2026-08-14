import { apiGet, apiPost } from "./client";
import type { Batch, BatchPreview, CreateBatchRequest } from "../types/batch";

// Mirrors app.modules.batch.router's pure GET /batches (list) plus the
// composition root app/api/v1/endpoints/batch_render.py, which owns every
// other batch endpoint -- see docs/features/40-batch-video-creation.md.

export function listBatches(): Promise<Batch[]> {
  return apiGet("/batches");
}

export function previewBatch(input: CreateBatchRequest): Promise<BatchPreview> {
  return apiPost("/batches/preview", input);
}

export function createBatch(input: CreateBatchRequest): Promise<Batch> {
  return apiPost("/batches", input);
}

export function getBatch(batchId: number): Promise<Batch> {
  return apiGet(`/batches/${batchId}`);
}

// Bounded-concurrency AI beat generation for every PROJECT_CREATED item --
// fires a background job and returns immediately; poll getBatch() (or
// syncBatch()) for progress, same "return immediately, poll for status"
// shape as render jobs elsewhere in this app.
export function generateBeatsForBatch(batchId: number): Promise<Batch> {
  return apiPost(`/batches/${batchId}/generate-beats`);
}

// Enqueues a real RenderJob (via the existing single-worker render queue --
// never a second one) for every eligible BEATS_READY item; ineligible ones
// are marked SKIPPED, not failing the whole batch.
export function renderBatch(batchId: number): Promise<Batch> {
  return apiPost(`/batches/${batchId}/render`);
}

// Pulls each RENDERING item's real VideoComposeJob status -- getBatch()
// already does this internally, so this is only needed for an explicit
// manual refresh action, not routine polling.
export function syncBatch(batchId: number): Promise<Batch> {
  return apiPost(`/batches/${batchId}/sync`);
}

export function cancelBatch(batchId: number): Promise<Batch> {
  return apiPost(`/batches/${batchId}/cancel`);
}

// Only retries FAILED/SKIPPED items -- a COMPLETED render is never touched
// or duplicated.
export function retryBatch(batchId: number): Promise<Batch> {
  return apiPost(`/batches/${batchId}/retry`);
}
