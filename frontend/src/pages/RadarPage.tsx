import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Loader2,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  Sparkles,
  Download,
  ShieldQuestion,
  AlertTriangle,
  Radar as RadarIcon,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { formatViews, formatDuration } from "../utils/format";
import {
  runSearch,
  listCollections,
  listSaved,
  saveResult,
  unsaveResult,
  findSimilar,
} from "../api/discovery";
import type {
  RadarPlatform,
  RadarResult,
  RadarSearch,
  RadarSort,
  SavedRadarResult,
} from "../types/discovery";
import "./RadarPage.css";

const PLATFORM_TABS: { value: RadarPlatform | "all"; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "reddit", label: "Reddit" },
  { value: "youtube", label: "YouTube" },
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
];

const SORTS: { value: RadarSort; label: string }[] = [
  { value: "best", label: "Tốt nhất" },
  { value: "newest", label: "Mới nhất" },
  { value: "most_viewed", label: "Nhiều view nhất" },
];

const PLATFORM_LABEL: Record<RadarPlatform, string> = {
  reddit: "Reddit",
  youtube: "YouTube",
  tiktok: "TikTok",
  instagram: "Instagram",
};

function relativeDate(iso: string | null): string {
  if (!iso) return "—";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "hôm nay";
  if (days === 1) return "1 ngày trước";
  if (days < 30) return `${days} ngày trước`;
  if (days < 365) return `${Math.floor(days / 30)} tháng trước`;
  return `${Math.floor(days / 365)} năm trước`;
}

export function RadarPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState<RadarPlatform | "all">("all");
  const [sort, setSort] = useState<RadarSort>("best");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<RadarSearch | null>(null);
  const [collections, setCollections] = useState<string[]>([]);
  const [saved, setSaved] = useState<SavedRadarResult[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [similarNote, setSimilarNote] = useState<string | null>(null);

  useEffect(() => {
    listCollections().then(setCollections).catch(() => setCollections([]));
    listSaved().then(setSaved).catch(() => setSaved([]));
  }, []);

  const savedIds = useMemo(() => new Set(saved.map((s) => s.id)), [saved]);

  const doSearch = useCallback(
    async (opts?: { sort?: RadarSort; platform?: RadarPlatform | "all"; query?: string }) => {
      const q = (opts?.query ?? query).trim();
      if (!q) return;
      const s = opts?.sort ?? sort;
      const p = opts?.platform ?? platform;
      setLoading(true);
      setError(null);
      setSimilarNote(null);
      setShowSaved(false);
      try {
        const result = await runSearch({
          query: q,
          sort: s,
          platforms: p === "all" ? null : [p],
        });
        setSearch(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Tìm kiếm thất bại.");
      } finally {
        setLoading(false);
      }
    },
    [query, sort, platform],
  );

  async function handleSave(result: RadarResult) {
    const isSaved = savedIds.has(result.id);
    try {
      if (isSaved) {
        await unsaveResult(result.id);
      } else {
        const collection =
          window.prompt(
            `Lưu vào bộ sưu tập nào?\n(${collections.join(", ")})`,
            result.content_tags[0]?.replace(/^r\//, "") || "Other",
          ) ?? "Other";
        await saveResult(result.id, collection.trim() || "Other");
      }
      setSaved(await listSaved());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không lưu được.");
    }
  }

  async function handleFindSimilar(result: RadarResult) {
    setLoading(true);
    setError(null);
    try {
      const res = await findSimilar(result.id);
      setSearch(res.search);
      setSimilarNote(`Giống với: ${res.keywords.slice(0, 5).join(" · ")}`);
      setShowSaved(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tìm được video tương tự.");
    } finally {
      setLoading(false);
    }
  }

  const visibleResults = showSaved ? saved : search?.results ?? [];

  return (
    <>
      <PageHeader
        title="Viral Source Radar"
        subtitle="Một ô tìm kiếm — quét Reddit, YouTube, TikTok, Instagram cùng lúc để tìm nguồn video short-form tiềm năng"
      />

      <div className="radar-search-row">
        <div className="radar-search-box">
          <Search size={18} />
          <input
            type="text"
            placeholder='Nhập chủ đề, ví dụ: "beard transformation"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
          />
        </div>
        <button className="btn btn-primary" onClick={() => doSearch()} disabled={loading || !query.trim()}>
          {loading ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
          Tìm
        </button>
      </div>

      <div className="radar-controls">
        <div className="radar-tabs">
          {PLATFORM_TABS.map((t) => (
            <button
              key={t.value}
              className={`radar-tab${platform === t.value ? " active" : ""}`}
              onClick={() => {
                setPlatform(t.value);
                if (search) doSearch({ platform: t.value });
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="radar-right-controls">
          <select
            className="radar-sort"
            value={sort}
            onChange={(e) => {
              const next = e.target.value as RadarSort;
              setSort(next);
              if (search) doSearch({ sort: next });
            }}
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <button
            className={`radar-tab${showSaved ? " active" : ""}`}
            onClick={() => setShowSaved((v) => !v)}
          >
            <Bookmark size={14} /> Đã lưu ({saved.length})
          </button>
        </div>
      </div>

      {error && <div className="radar-alert radar-alert-error">{error}</div>}
      {similarNote && <div className="radar-alert radar-alert-info">{similarNote}</div>}

      {!showSaved && search && (
        <div className="radar-engine-strip">
          {search.engine_statuses.map((s) => (
            <span key={s.platform} className={`radar-engine radar-engine--${s.status}`} title={s.error ?? ""}>
              {PLATFORM_LABEL[s.platform]}{" "}
              {s.status === "ok" ? `✓ ${s.result_count}` : s.status === "unavailable" ? "— n/a" : "⚠"}
            </span>
          ))}
          <span className="radar-engine-summary">
            {search.unique_count} video · {search.total_before_dedup} kết quả thô
          </span>
        </div>
      )}

      {loading && !search && (
        <div className="radar-loading">
          <Loader2 size={28} className="spin" /> Đang quét các nền tảng…
        </div>
      )}

      {!loading && visibleResults.length === 0 && (
        <EmptyState
          icon={RadarIcon}
          title={showSaved ? "Chưa lưu video nào" : search ? "Không có kết quả" : "Nhập chủ đề để bắt đầu"}
          description={
            showSaved
              ? "Bấm Lưu trên một thẻ kết quả để thêm vào đây."
              : "Ví dụ: beard transformation, couple reaction, glow up, rescue dog."
          }
        />
      )}

      <div className="radar-grid">
        {visibleResults.map((r) => (
          <RadarCard
            key={`${r.platform}-${r.id}`}
            result={r}
            saved={savedIds.has(r.id)}
            onSave={() => handleSave(r)}
            onFindSimilar={() => handleFindSimilar(r)}
            onDownload={() => navigate(`/download?url=${encodeURIComponent(r.source_url)}`)}
          />
        ))}
      </div>
    </>
  );
}

function RadarCard({
  result,
  saved,
  onSave,
  onFindSimilar,
  onDownload,
}: {
  result: RadarResult;
  saved: boolean;
  onSave: () => void;
  onFindSimilar: () => void;
  onDownload: () => void;
}) {
  const b = result.score_breakdown;
  const canDownload = result.download_capability === "ALLOWED";
  const ar =
    result.aspect_ratio == null ? null : result.aspect_ratio < 0.9 ? "9:16" : result.aspect_ratio > 1.2 ? "16:9" : "1:1";

  return (
    <div className="radar-card">
      <div className="radar-thumb-wrap">
        {result.thumbnail_url ? (
          <img className="radar-thumb" src={result.thumbnail_url} alt="" loading="lazy" />
        ) : (
          <div className="radar-thumb radar-thumb--empty" />
        )}
        <span className="radar-score-badge">{Math.round(result.viral_score)}</span>
        {result.duration_sec != null && (
          <span className="radar-dur-badge">{formatDuration(result.duration_sec)}</span>
        )}
      </div>

      <div className="radar-card-body">
        <div className="radar-card-top">
          <span className={`radar-plat radar-plat--${result.platform}`}>
            {PLATFORM_LABEL[result.platform]}
          </span>
          {result.also_on.map((p) => (
            <span key={p} className="radar-alsoon" title="Cùng video xuất hiện trên">
              +{PLATFORM_LABEL[p]}
            </span>
          ))}
          {ar && <span className="radar-ar">{ar}</span>}
        </div>

        <h3 className="radar-card-title" title={result.title}>
          {result.title}
        </h3>

        <div className="radar-card-meta">
          {result.creator_name && <span>{result.creator_name}</span>}
          {result.views != null && <span>{formatViews(result.views)} views</span>}
          {result.likes != null && <span>{formatViews(result.likes)} likes</span>}
          {result.comments != null && <span>{formatViews(result.comments)} bình luận</span>}
          <span>{relativeDate(result.published_at)}</span>
        </div>

        <div className="radar-breakdown">
          {(
            [
              ["Liên quan", b.relevance],
              ["Tương tác", b.engagement],
              ["Mới", b.recency],
              ["Short-form", b.short_form],
            ] as const
          ).map(([label, val]) => (
            <div key={label} className="radar-bd-row">
              <span>{label}</span>
              <span className="radar-bd-bar">
                <span style={{ width: `${Math.max(2, Math.min(100, val))}%` }} />
              </span>
              <span className="radar-bd-val">{Math.round(val)}</span>
            </div>
          ))}
        </div>

        <div className={`radar-rights radar-rights--${canDownload ? "ok" : "warn"}`}>
          {canDownload ? (
            <>
              <Download size={13} /> {result.rights_status === "CREATIVE_COMMONS" ? "Creative Commons" : "Cho phép tải"}
            </>
          ) : (
            <>
              <ShieldQuestion size={13} /> Cần xin phép ({result.rights_status})
            </>
          )}
        </div>

        <div className="radar-actions">
          <a className="btn" href={result.source_url} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Mở
          </a>
          <button className="btn" onClick={onSave}>
            {saved ? <BookmarkCheck size={14} /> : <Bookmark size={14} />} {saved ? "Đã lưu" : "Lưu"}
          </button>
          <button className="btn" onClick={onFindSimilar}>
            <Sparkles size={14} /> Tương tự
          </button>
          {canDownload ? (
            <button className="btn btn-primary" onClick={onDownload}>
              <Download size={14} /> Tải
            </button>
          ) : (
            <span className="radar-nodl" title="Nội dung chưa rõ bản quyền — không có nút Tải">
              <AlertTriangle size={13} /> Không tải
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
