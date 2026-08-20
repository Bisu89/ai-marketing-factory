// Mirrors backend/app/modules/content_strategy/schemas.py exactly -- see
// docs/features/65-content-strategy-api.md.

export interface Pillar {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Format {
  id: number;
  pillar_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

// Mirrors backend CONTENT_IDEA_STATUSES.
export type IdeaStatus = "draft" | "approved" | "rejected" | "used";

export interface Idea {
  id: number;
  pillar_id: number;
  format_id: number;
  title: string;
  premise: string | null;
  target_emotion_id: number | null;
  commercial_intent: string | null;
  score: number | null;
  status: IdeaStatus;
  created_at: string;
  updated_at: string;
}

export interface IdeaListResponse {
  items: Idea[];
  total: number;
  page: number;
  page_size: number;
}

export interface IdeaListParams {
  pillar_id?: number;
  format_id?: number;
  status?: IdeaStatus;
  min_score?: number;
  page: number;
  page_size: number;
}

export interface IdeaCreateInput {
  pillar_id: number;
  format_id: number;
  title: string;
  premise?: string;
  target_emotion_id?: number;
  commercial_intent?: string;
  status?: IdeaStatus;
}

export interface IdeaUpdateInput {
  title?: string;
  premise?: string;
  target_emotion_id?: number;
  commercial_intent?: string;
  score?: number;
  status?: IdeaStatus;
}
