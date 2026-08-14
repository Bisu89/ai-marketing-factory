import { config } from "../config/env";

async function extractErrorMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);
  if (Array.isArray(body?.detail)) {
    // FastAPI's own request-body-validation shape (a Pydantic model failing
    // to validate): a list of {loc, msg, ...} objects. Join their messages
    // instead of dumping the raw JSON array on the user.
    const messages = body.detail.map((item: { msg?: string }) => item?.msg).filter(Boolean);
    if (messages.length > 0) return messages.join("\n");
  }
  if (body?.detail) {
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  }
  return `API request failed: ${response.status}`;
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`);
  return handle<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(response);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    method: "POST",
    body: formData,
  });
  return handle<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, { method: "DELETE" });
  return handle<T>(response);
}

export function mediaUrl(path: string): string {
  // Channel/video-id path segments can contain spaces or other characters
  // that need percent-encoding to be a valid URL (e.g. "Adventure Vlogs").
  const encodedPath = path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${config.apiBaseUrl.replace(/\/api\/v1$/, "")}${encodedPath}`;
}
