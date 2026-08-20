// Mirrors backend/app/schemas/winner_detection.py exactly -- see
// docs/features/73-winner-detection.md.

export interface WinnerGroupStats {
  dimension: string;
  label: string;

  sample_size: number;
  linked_sample_size: number;
  min_sample_size: number;
  meets_minimum_sample: boolean;
  confidence: "insufficient" | "low" | "medium" | "high";

  avg_views: number | null;
  median_views: number | null;
  avg_engagement_rate: number | null;
  avg_share_rate: number | null;
  avg_follower_conversion_rate: number | null;
  avg_views_per_day_since_publish: number | null;

  performance_score: number | null;
  performance_score_basis: string;
  note: string | null;
}

export interface TrendGroupStats {
  dimension: string;
  label: string;
  trend: "rising" | "underperforming" | "stable" | "insufficient_data";
  earlier_avg_score: number | null;
  recent_avg_score: number | null;
  change_pct: number | null;
  note: string;
}
