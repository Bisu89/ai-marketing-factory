import { apiDelete, apiGet, apiPost } from "./client";
import type { ProjectConfig, Template } from "../types/videoFactory";

// Mirrors backend/app/modules/beat/router.py's GET/POST/DELETE /templates
// -- see docs/features/39-project-templates.md. Built-in templates are
// fixed Python constants (always the first 3 results); custom ones are
// persisted in templates.json.
export function listTemplates(): Promise<Template[]> {
  return apiGet("/templates");
}

export interface CreateTemplateInput {
  name: string;
  description?: string;
  config: ProjectConfig;
}

export function createTemplate(input: CreateTemplateInput): Promise<Template> {
  return apiPost("/templates", input);
}

export function deleteTemplate(templateId: string): Promise<void> {
  return apiDelete(`/templates/${templateId}`);
}
