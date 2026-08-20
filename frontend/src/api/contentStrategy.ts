import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type {
  Format,
  Idea,
  IdeaCreateInput,
  IdeaListParams,
  IdeaListResponse,
  IdeaUpdateInput,
  Pillar,
} from "../features/contentStudio/types";

export function fetchPillars(): Promise<Pillar[]> {
  return apiGet("/content-pillars");
}

export function fetchFormats(pillarId?: number): Promise<Format[]> {
  const query = pillarId != null ? `?pillar_id=${pillarId}` : "";
  return apiGet(`/content-formats${query}`);
}

function buildIdeaQuery(params: IdeaListParams): string {
  const search = new URLSearchParams();
  search.set("page", String(params.page));
  search.set("page_size", String(params.page_size));
  if (params.pillar_id != null) search.set("pillar_id", String(params.pillar_id));
  if (params.format_id != null) search.set("format_id", String(params.format_id));
  if (params.status) search.set("status", params.status);
  if (params.min_score != null) search.set("min_score", String(params.min_score));
  return search.toString();
}

export function fetchIdeas(params: IdeaListParams): Promise<IdeaListResponse> {
  return apiGet(`/content-ideas?${buildIdeaQuery(params)}`);
}

export function createIdea(input: IdeaCreateInput): Promise<Idea> {
  return apiPost("/content-ideas", input);
}

export function updateIdea(ideaId: number, patch: IdeaUpdateInput): Promise<Idea> {
  return apiPatch(`/content-ideas/${ideaId}`, patch);
}

export function deleteIdea(ideaId: number): Promise<void> {
  return apiDelete(`/content-ideas/${ideaId}`);
}
