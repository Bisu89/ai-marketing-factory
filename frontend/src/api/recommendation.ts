import { apiGet } from "./client";
import type { Recommendation } from "../types/recommendation";

// Read-only advice, never a trigger for generation -- see
// docs/features/74-content-learning-loop.md's own "do not silently
// manipulate generation" note.
export function getContentRecommendations(limit = 6): Promise<Recommendation[]> {
  return apiGet(`/recommendations/content?limit=${limit}`);
}
