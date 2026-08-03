import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import type { CategoryOut, EmotionOut, VideoListParams } from "../types";
import { STATUS_LABELS, STATUS_ORDER } from "./StatusBadge";
import "./LibraryFilters.css";

const PLATFORMS = ["youtube", "tiktok", "facebook", "instagram"];
const DURATIONS: { value: string; label: string }[] = [
  { value: "<30", label: "< 30s" },
  { value: "30-60", label: "30–60s" },
  { value: "1-3min", label: "1–3 phút" },
  { value: ">3min", label: "> 3 phút" },
];
const RESOLUTIONS: { value: string; label: string }[] = [
  { value: "720", label: "720p" },
  { value: "1080", label: "1080p" },
  { value: "4k", label: "4K" },
];
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "newest", label: "Mới nhất" },
  { value: "oldest", label: "Cũ nhất" },
  { value: "title", label: "Tiêu đề" },
  { value: "duration", label: "Thời lượng" },
  { value: "download_date", label: "Ngày tải" },
  { value: "file_size", label: "Dung lượng" },
  { value: "channel", label: "Kênh" },
  { value: "platform", label: "Nền tảng" },
];

interface LibraryFiltersProps {
  filters: VideoListParams;
  categories: CategoryOut[];
  emotions: EmotionOut[];
  onChange: (patch: Partial<VideoListParams>) => void;
}

export function LibraryFilters({ filters, categories, emotions, onChange }: LibraryFiltersProps) {
  const [searchDraft, setSearchDraft] = useState(filters.search ?? "");

  // Debounced so a search request doesn't fire on every keystroke; synced
  // back if the URL's search param changes from outside (e.g. browser back).
  useEffect(() => setSearchDraft(filters.search ?? ""), [filters.search]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchDraft !== (filters.search ?? "")) onChange({ search: searchDraft || undefined });
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft]);

  const hasActiveFilters =
    filters.platform || filters.status || filters.category_id != null || filters.emotion_id != null ||
    filters.favorite != null || filters.duration || filters.resolution;

  return (
    <div className="library-filters">
      <div className="library-search-row">
        <Search size={15} />
        <input
          type="text"
          placeholder="Tìm theo tiêu đề, kênh, tag..."
          value={searchDraft}
          onChange={(e) => setSearchDraft(e.target.value)}
        />
      </div>

      <div className="library-filter-controls">
        <select value={filters.platform ?? ""} onChange={(e) => onChange({ platform: e.target.value || undefined })}>
          <option value="">Mọi nền tảng</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <select value={filters.status ?? ""} onChange={(e) => onChange({ status: e.target.value || undefined })}>
          <option value="">Mọi trạng thái</option>
          {[...STATUS_ORDER, "deleted"].map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>

        <select
          value={filters.category_id ?? ""}
          onChange={(e) => onChange({ category_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Mọi topic</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={filters.emotion_id ?? ""}
          onChange={(e) => onChange({ emotion_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Mọi emotion</option>
          {emotions.map((em) => (
            <option key={em.id} value={em.id}>
              {em.name}
            </option>
          ))}
        </select>

        <select value={filters.duration ?? ""} onChange={(e) => onChange({ duration: e.target.value || undefined })}>
          <option value="">Mọi độ dài</option>
          {DURATIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>

        <select
          value={filters.resolution ?? ""}
          onChange={(e) => onChange({ resolution: e.target.value || undefined })}
        >
          <option value="">Mọi độ phân giải</option>
          {RESOLUTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>

        <label className="library-favorite-toggle">
          <input
            type="checkbox"
            checked={filters.favorite === true}
            onChange={(e) => onChange({ favorite: e.target.checked ? true : undefined })}
          />
          Yêu thích
        </label>

        {hasActiveFilters && (
          <button
            className="library-filter-clear"
            onClick={() =>
              onChange({
                platform: undefined,
                status: undefined,
                category_id: undefined,
                emotion_id: undefined,
                favorite: undefined,
                duration: undefined,
                resolution: undefined,
              })
            }
          >
            Xoá bộ lọc
          </button>
        )}

        <select className="library-sort-select" value={filters.sort} onChange={(e) => onChange({ sort: e.target.value })}>
          {SORT_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              Sắp xếp: {s.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
