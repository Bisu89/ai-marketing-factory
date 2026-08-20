// Mirrors backend/app/schemas/ai_cost.py exactly -- see
// docs/features/75-ai-cost-tracking.md.

export interface AICallCost {
  id: number;
  kind: string;
  job_id: number | null;
  video_id: number;
  provider: string;
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number;
  cost_usd: number | null;
  cost_note: string | null;
  confirmed_price: boolean;
  created_at: string;
}

export interface GroupCost {
  label: string;
  total_cost_usd: number;
  call_count: number;
  unpriced_call_count: number;
  all_confirmed: boolean;
}

export interface StoryCost {
  story_job_id: number;
  video_id: number;
  total_cost_usd: number;
  call_count: number;
  unpriced_call_count: number;
}

export interface BatchCost {
  batch_id: number;
  batch_name: string;
  total_cost_usd: number;
  story_count: number;
  unpriced_call_count: number;
}

export interface VideoCost {
  video_compose_job_id: number;
  project_id: number | null;
  image_cost_usd: number | null;
  image_count: number | null;
}

export interface AICostSummary {
  total_ai_cost_usd: number;
  total_calls: number;
  unpriced_call_count: number;
  videos_generated: number;
  average_cost_per_video_usd: number | null;
  average_cost_per_video_note: string;
  cost_per_1000_videos_usd: number | null;
  by_provider: GroupCost[];
  by_model: GroupCost[];
  by_month: GroupCost[];
}
