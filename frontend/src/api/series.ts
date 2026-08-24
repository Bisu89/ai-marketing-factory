import { apiGet, apiPost, apiPut } from "./client";
import type { CreateSeriesRequest, Series, SeriesProjectSummary, UpdateSeriesRequest } from "../types/series";
import type { Project } from "../types/videoFactory";

// Mirrors app.modules.series.router's pure CRUD plus the composition root
// app/api/v1/endpoints/series_project.py, which owns attach/list-episodes.

export function listSeries(): Promise<Series[]> {
  return apiGet("/series");
}

export function createSeries(input: CreateSeriesRequest): Promise<Series> {
  return apiPost("/series", input);
}

export function getSeries(seriesId: number): Promise<Series> {
  return apiGet(`/series/${seriesId}`);
}

export function updateSeries(seriesId: number, input: UpdateSeriesRequest): Promise<Series> {
  return apiPut(`/series/${seriesId}`, input);
}

export function listSeriesProjects(seriesId: number): Promise<SeriesProjectSummary[]> {
  return apiGet(`/series/${seriesId}/projects`);
}

// Folds the series' own character_description into the project's
// image_style_prompt (a one-time snapshot, not a live link -- see
// series_project.py's own docstring) and assigns the next episode_number.
export function attachProjectToSeries(projectId: number, seriesId: number): Promise<Project> {
  return apiPost(`/projects/${projectId}/attach-series`, { series_id: seriesId });
}
