import { LayoutGrid, List } from "lucide-react";
import type { ViewMode } from "../types";
import "./ViewToggle.css";

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    <div className="view-toggle" role="group" aria-label="Chế độ xem">
      <button
        type="button"
        className={value === "grid" ? "active" : ""}
        onClick={() => onChange("grid")}
        aria-label="Grid view"
        title="Grid view"
      >
        <LayoutGrid size={16} />
      </button>
      <button
        type="button"
        className={value === "table" ? "active" : ""}
        onClick={() => onChange("table")}
        aria-label="Table view"
        title="Table view"
      >
        <List size={16} />
      </button>
    </div>
  );
}
