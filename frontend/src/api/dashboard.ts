import { apiGet } from "./client";
import type { DashboardOut } from "../types/dashboard";

export function getDashboard(): Promise<DashboardOut> {
  return apiGet<DashboardOut>("/dashboard");
}
