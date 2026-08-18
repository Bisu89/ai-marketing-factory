import { apiGet, apiPost, apiPut } from "./client";
import type { PackageOverrides, ReadyToPostPackage } from "../types/package";

// Mirrors app/api/v1/endpoints/package_generate.py -- see
// docs/features/53-thumbnail-metadata-package.md.

export function getProjectPackage(projectId: number): Promise<ReadyToPostPackage> {
  return apiGet(`/projects/${projectId}/package`);
}

export function setPackageOverrides(projectId: number, overrides: PackageOverrides): Promise<{ project_id: number }> {
  return apiPut(`/projects/${projectId}/package-overrides`, overrides);
}

export function regeneratePackage(projectId: number): Promise<{ project_id: number; generated: boolean }> {
  return apiPost(`/projects/${projectId}/regenerate-package`);
}

export function regenerateThumbnail(projectId: number): Promise<{ project_id: number; generated: boolean }> {
  return apiPost(`/projects/${projectId}/regenerate-thumbnail`);
}

export function regenerateMetadata(projectId: number): Promise<{ project_id: number; generated: boolean }> {
  return apiPost(`/projects/${projectId}/regenerate-metadata`);
}
