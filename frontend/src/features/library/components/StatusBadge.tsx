import "./StatusBadge.css";

const STATUS_LABELS: Record<string, string> = {
  unused: "Unused",
  processing: "Processing",
  published: "Published",
  archived: "Archived",
  deleted: "Deleted",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-badge--${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}
