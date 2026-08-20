import { apiGet } from "./client";
import type { AICallCost, AICostSummary, BatchCost, StoryCost, VideoCost } from "../types/aiCost";

export function getAICostSummary(): Promise<AICostSummary> {
  return apiGet("/ai-costs/summary");
}

export function getAICostCalls(limit = 100): Promise<AICallCost[]> {
  return apiGet(`/ai-costs/calls?limit=${limit}`);
}

export function getAICostStories(): Promise<StoryCost[]> {
  return apiGet("/ai-costs/stories");
}

export function getAICostBatches(): Promise<BatchCost[]> {
  return apiGet("/ai-costs/batches");
}

export function getAICostVideos(): Promise<VideoCost[]> {
  return apiGet("/ai-costs/videos");
}
