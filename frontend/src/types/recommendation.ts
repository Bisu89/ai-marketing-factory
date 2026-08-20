// Mirrors backend/app/schemas/recommendation.py exactly -- see
// docs/features/74-content-learning-loop.md.

export interface Recommendation {
  dimension: "pillar" | "format" | "hook" | "emotion";
  label: string;

  weight: number;
  historical_performance: number;
  sample_confidence: number;
  recency_factor: number;

  confidence_tier: "insufficient" | "low" | "medium" | "high";
  trend: "rising" | "stable" | "underperforming" | "insufficient_data";
  sample_size: number;
  linked_sample_size: number;

  reasons: string[];
}
