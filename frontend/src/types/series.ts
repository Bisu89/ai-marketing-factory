// Mirrors backend/app/modules/series/schemas.py + the composition root
// app/api/v1/endpoints/series_project.py -- see
// docs/features -- Series (scoped-down "100-Day Series"). A Series is a
// standing container (name + character/visual description) that
// independently-authored Projects (each still created exactly like today's
// existing "New Video" flow -- no AI-planned story arc) attach to, so their
// AI-generated images share one character description.

export interface Series {
  id: number;
  name: string;
  character_description: string;
  created_at: string;
  updated_at: string;
}

export interface CreateSeriesRequest {
  name: string;
  character_description?: string;
}

export interface UpdateSeriesRequest {
  name: string;
  character_description?: string;
}

// Mirrors series_project.py's SeriesProjectSummary -- a lightweight per-
// episode row for the series detail page, not a full Project.
export interface SeriesProjectSummary {
  id: number;
  name: string;
  episode_number: number | null;
  render_job_id: number | null;
}
