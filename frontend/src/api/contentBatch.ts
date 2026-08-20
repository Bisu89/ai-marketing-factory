import { apiGet, apiPost } from "./client";
import type { ContentBatch, ContentBatchCreateInput } from "../types/contentBatch";

export function listContentBatches(): Promise<ContentBatch[]> {
  return apiGet("/content-batches");
}

export function getContentBatch(batchId: number): Promise<ContentBatch> {
  return apiGet(`/content-batches/${batchId}`);
}

export function createContentBatch(input: ContentBatchCreateInput): Promise<ContentBatch> {
  return apiPost("/content-batches", input);
}

// Fires the bounded-concurrency background run and returns immediately --
// poll getContentBatch() for progress, same "return immediately, poll for
// status" shape as the existing script/idea Batch (api/batch.ts).
export function runContentBatch(batchId: number): Promise<ContentBatch> {
  return apiPost(`/content-batches/${batchId}/run`);
}

export function cancelContentBatch(batchId: number): Promise<ContentBatch> {
  return apiPost(`/content-batches/${batchId}/cancel`);
}

export function retryContentBatchItem(batchId: number, itemId: number): Promise<ContentBatch> {
  return apiPost(`/content-batches/${batchId}/items/${itemId}/retry`);
}
