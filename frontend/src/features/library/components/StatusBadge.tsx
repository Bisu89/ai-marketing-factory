import "./StatusBadge.css";

// Content workflow order, not download state -- matches backend
// VIDEO_STATUSES (app/models/video.py). "deleted" is a soft-delete marker
// outside the visible workflow, so it's excluded from the edit dropdown's
// option order but still has a label/color for display on already-deleted
// rows.
export const STATUS_ORDER = ["downloaded", "ready", "published", "archived"] as const;

export const STATUS_LABELS: Record<string, string> = {
  downloaded: "Downloaded",
  ready: "Ready",
  published: "Published",
  archived: "Archived",
  deleted: "Deleted",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-badge--${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}
