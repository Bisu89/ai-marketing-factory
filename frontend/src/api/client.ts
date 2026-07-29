import { config } from "../config/env";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
