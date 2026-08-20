import { ChevronLeft, ChevronRight } from "lucide-react";
import "./Pagination.css";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
  itemLabel?: string;
}

export function Pagination({ page, pageSize, total, onChange, itemLabel = "video" }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="pagination">
      <span className="pagination-summary">
        {total} {itemLabel}
      </span>
      <div className="pagination-controls">
        <button disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Trang trước">
          <ChevronLeft size={16} />
        </button>
        <span>
          Trang {page}/{totalPages}
        </span>
        <button disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Trang sau">
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
