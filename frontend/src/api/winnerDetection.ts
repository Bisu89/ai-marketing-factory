import { apiGet } from "./client";
import type { TrendGroupStats, WinnerGroupStats } from "../types/winnerDetection";

export function getWinnerFormats(minSampleSize: number): Promise<WinnerGroupStats[]> {
  return apiGet(`/winners/formats?min_sample_size=${minSampleSize}`);
}

export function getWinnerHooks(minSampleSize: number): Promise<WinnerGroupStats[]> {
  return apiGet(`/winners/hooks?min_sample_size=${minSampleSize}`);
}

export function getWinnerPillars(minSampleSize: number): Promise<WinnerGroupStats[]> {
  return apiGet(`/winners/pillars?min_sample_size=${minSampleSize}`);
}

export function getRisingFormats(minSampleSize: number): Promise<TrendGroupStats[]> {
  return apiGet(`/winners/formats/rising?min_sample_size=${minSampleSize}`);
}

export function getUnderperformingFormats(minSampleSize: number): Promise<WinnerGroupStats[]> {
  return apiGet(`/winners/formats/underperforming?min_sample_size=${minSampleSize}`);
}
