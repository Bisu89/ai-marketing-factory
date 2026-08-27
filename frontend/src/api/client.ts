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

// The API is dynamic data, never a cacheable asset -- always hit the
// network. A packaged build once served the SPA's index.html as the
// fallback for unknown /api/v1/* paths *with* ETag/Last-Modified headers,
// which some browsers then heuristically cached and replayed ("200 OK
// (from disk cache)", content-type text/html) even after the real endpoint
// existed. `no-store` makes that impossible.
const NO_STORE: RequestInit = { cache: "no-store" };

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, NO_STORE);
  return handle<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...NO_STORE,
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(response);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...NO_STORE,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...NO_STORE,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...NO_STORE,
    method: "POST",
    body: formData,
  });
  return handle<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, { ...NO_STORE, method: "DELETE" });
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
