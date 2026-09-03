import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Check,
  ExternalLink,
  Loader2,
  Newspaper,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { listTemplates } from "../api/template";
import {
  createNewsBatch,
  createNewsSource,
  deleteNewsSource,
  dismissNewsItem,
  draftNewsScripts,
  fetchAllNewsSources,
  fetchNewsItems,
  fetchNewsSource,
  fetchNewsSources,
  updateNewsSource,
} from "../api/news";
import type { NewsItem, NewsItemStatus, NewsSource } from "../types/news";
import type { Template } from "../types/videoFactory";
import "./NewsPage.css";

const STATUS_TABS: { value: NewsItemStatus; label: string }[] = [
  { value: "new", label: "Mới" },
  { value: "drafted", label: "Đã có script" },
  { value: "queued", label: "Đã lên hàng đợi" },
  { value: "used", label: "Đã dùng" },
  { value: "dismissed", label: "Đã ẩn" },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "vừa xong";
  if (mins < 60) return `${mins} phút trước`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} giờ trước`;
  return `${Math.round(hrs / 24)} ngày trước`;
}

export function NewsPage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [statusTab, setStatusTab] = useState<NewsItemStatus>("new");
  const [sourceFilter, setSourceFilter] = useState<number | "">("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);

  const loadSources = useCallback(async () => {
    try {
      setSources(await fetchNewsSources());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được nguồn tin.");
    }
  }, []);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchNewsItems({
        status: statusTab,
        source_id: sourceFilter === "" ? undefined : sourceFilter,
        page_size: 150,
      });
      setItems(res.items);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được tin.");
    } finally {
      setLoading(false);
    }
  }, [statusTab, sourceFilter]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);
  useEffect(() => {
    loadItems();
  }, [loadItems]);

  async function handleFetchAll() {
    setBusy("fetch");
    setError(null);
    setNotice(null);
    try {
      const res = await fetchAllNewsSources();
      const failed = res.results.filter((r) => r.error);
      setNotice(
        `Đã kéo ${res.total_new_items} tin mới` +
          (failed.length ? ` — ${failed.length} nguồn lỗi (xem "Nguồn tin").` : "."),
      );
      await Promise.all([loadSources(), loadItems()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kéo tin thất bại.");
    } finally {
      setBusy(null);
    }
  }

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const selectableIds = useMemo(
    () => items.filter((i) => i.status === "new" || i.status === "drafted").map((i) => i.id),
    [items],
  );
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));

  async function handleDraft() {
    const ids = [...selected];
    if (ids.length === 0) return;
    setBusy("draft");
    setError(null);
    setNotice(null);
    try {
      const res = await draftNewsScripts(ids);
      setNotice(
        res.errors.length
          ? res.errors.join(" · ")
          : `Đã tạo ${res.drafted} script.`,
      );
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo script thất bại.");
    } finally {
      setBusy(null);
    }
  }

  const selectedDraftedCount = useMemo(
    () => items.filter((i) => selected.has(i.id) && i.status === "drafted" && i.script_text).length,
    [items, selected],
  );

  return (
    <>
      <PageHeader
        title="Tin tức"
        subtitle="Kéo bài từ RSS của các báo → chọn tin → tạo script → sản xuất video hàng loạt qua Batch."
        actions={
          <>
            <button className="btn btn-secondary" onClick={() => setShowSources((v) => !v)}>
              Nguồn tin ({sources.length})
            </button>
            <button className="btn btn-primary" onClick={handleFetchAll} disabled={busy === "fetch"}>
              {busy === "fetch" ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
              Kéo tất cả
            </button>
          </>
        }
      />

      {error && <div className="news-alert news-alert-error">{error}</div>}
      {notice && <div className="news-alert news-alert-info">{notice}</div>}

      {showSources && (
        <SourcesPanel
          sources={sources}
          busy={busy}
          setBusy={setBusy}
          onChanged={loadSources}
          onFetched={async () => {
            await Promise.all([loadSources(), loadItems()]);
          }}
          onError={setError}
        />
      )}

      <div className="news-toolbar">
        <div className="news-tabs">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              className={`news-tab${statusTab === tab.value ? " active" : ""}`}
              onClick={() => setStatusTab(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <select
          className="news-source-select"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">Tất cả nguồn</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {(statusTab === "new" || statusTab === "drafted") && selectableIds.length > 0 && (
        <div className="news-selectbar">
          <label className="news-check">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(e) => setSelected(e.target.checked ? new Set(selectableIds) : new Set())}
            />
            <span>{selected.size > 0 ? `Đã chọn ${selected.size}` : "Chọn tất cả"}</span>
          </label>
          <div className="news-selectbar-actions">
            <button
              className="btn btn-secondary"
              disabled={selected.size === 0 || busy === "draft"}
              onClick={handleDraft}
            >
              {busy === "draft" ? <Loader2 size={14} className="spin" /> : null}
              Tạo script ({selected.size})
            </button>
            <button
              className="btn btn-primary"
              disabled={selectedDraftedCount === 0}
              onClick={() => setBatchOpen(true)}
              title={selectedDraftedCount === 0 ? "Cần tạo script trước" : ""}
            >
              Tạo Batch ({selectedDraftedCount})
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="news-loading">
          <Loader2 size={18} className="spin" /> Đang tải…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title="Chưa có tin"
          description='Bấm "Kéo tất cả" để lấy bài mới nhất từ các nguồn RSS đã cấu hình.'
        />
      ) : (
        <ul className="news-list">
          {items.map((item) => {
            const selectable = item.status === "new" || item.status === "drafted";
            return (
              <li key={item.id} className={`news-item${selected.has(item.id) ? " selected" : ""}`}>
                {selectable && (
                  <input
                    type="checkbox"
                    className="news-item-check"
                    checked={selected.has(item.id)}
                    onChange={() => toggle(item.id)}
                  />
                )}
                {item.image_url && (
                  <img className="news-item-thumb" src={item.image_url} alt="" loading="lazy" />
                )}
                <div className="news-item-body">
                  <div className="news-item-title">{item.title}</div>
                  {item.summary && <p className="news-item-summary">{item.summary}</p>}
                  <div className="news-item-meta">
                    <span>{item.source_name}</span>
                    {item.published_at && <span>· {timeAgo(item.published_at)}</span>}
                    {item.link && (
                      <a href={item.link} target="_blank" rel="noreferrer">
                        <ExternalLink size={12} /> Bài gốc
                      </a>
                    )}
                    {item.status === "drafted" && (
                      <span className="news-badge news-badge-ok">
                        <Check size={11} /> Đã có script
                      </span>
                    )}
                    {item.status === "queued" && item.batch_id && (
                      <button
                        className="news-linkbtn"
                        onClick={() => navigate(`/batches/${item.batch_id}`)}
                      >
                        Xem Batch #{item.batch_id}
                      </button>
                    )}
                  </div>
                  {item.script_text && (
                    <details className="news-item-script">
                      <summary>Xem script</summary>
                      <pre>{item.script_text}</pre>
                    </details>
                  )}
                </div>
                {selectable && (
                  <button
                    className="btn btn-icon news-item-dismiss"
                    title="Ẩn tin này"
                    onClick={async () => {
                      await dismissNewsItem(item.id);
                      loadItems();
                    }}
                  >
                    <X size={14} />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {batchOpen && (
        <CreateBatchModal
          count={selectedDraftedCount}
          itemIds={items
            .filter((i) => selected.has(i.id) && i.status === "drafted" && i.script_text)
            .map((i) => i.id)}
          onClose={() => setBatchOpen(false)}
          onCreated={(batchId) => navigate(`/batches/${batchId}`)}
        />
      )}
    </>
  );
}

function SourcesPanel({
  sources,
  busy,
  setBusy,
  onChanged,
  onFetched,
  onError,
}: {
  sources: NewsSource[];
  busy: string | null;
  setBusy: (v: string | null) => void;
  onChanged: () => Promise<void> | void;
  onFetched: () => Promise<void> | void;
  onError: (v: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState("");

  async function handleAdd() {
    if (!name.trim() || !url.trim()) return;
    setBusy("add-source");
    onError(null);
    try {
      await createNewsSource({ name, feed_url: url, category: category || null });
      setName("");
      setUrl("");
      setCategory("");
      await onChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Thêm nguồn thất bại.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="news-sources">
      <div className="news-sources-add">
        <input placeholder="Tên nguồn (VnExpress - Thế giới)" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="URL RSS (https://…/rss.xml)" value={url} onChange={(e) => setUrl(e.target.value)} />
        <input placeholder="Nhãn (tuỳ chọn)" value={category} onChange={(e) => setCategory(e.target.value)} />
        <button className="btn btn-primary" onClick={handleAdd} disabled={busy === "add-source" || !name.trim() || !url.trim()}>
          {busy === "add-source" ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
          Thêm
        </button>
      </div>
      <table className="news-sources-table">
        <tbody>
          {sources.map((s) => (
            <tr key={s.id}>
              <td>
                <label className="news-check">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={async (e) => {
                      await updateNewsSource(s.id, { enabled: e.target.checked });
                      onChanged();
                    }}
                  />
                  <span>{s.name}</span>
                </label>
                {s.last_error && (
                  <span className="news-source-err">
                    <AlertCircle size={11} /> {s.last_error}
                  </span>
                )}
              </td>
              <td className="news-source-cat">{s.category ?? "—"}</td>
              <td className="news-source-pending">{s.pending_items ? `${s.pending_items} chờ` : ""}</td>
              <td className="news-source-actions">
                <button
                  className="btn btn-icon"
                  title="Kéo nguồn này"
                  onClick={async () => {
                    setBusy(`fetch-${s.id}`);
                    try {
                      await fetchNewsSource(s.id);
                      await onFetched();
                    } catch (err) {
                      onError(err instanceof Error ? err.message : "Kéo thất bại.");
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  {busy === `fetch-${s.id}` ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
                </button>
                <button
                  className="btn btn-icon"
                  title="Xoá nguồn"
                  onClick={async () => {
                    if (!confirm(`Xoá nguồn "${s.name}"? Các tin đã kéo cũng bị xoá.`)) return;
                    await deleteNewsSource(s.id);
                    onChanged();
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreateBatchModal({
  count,
  itemIds,
  onClose,
  onCreated,
}: {
  count: number;
  itemIds: number[];
  onClose: () => void;
  onCreated: (batchId: number) => void;
}) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState("news_vi");
  const [name, setName] = useState(() => `Tin tức ${new Date().toISOString().slice(0, 10)}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    (async () => {
      try {
        const list = await listTemplates();
        if (!mounted.current) return;
        setTemplates(list);
        if (!list.some((t) => t.id === "news_vi") && list.length > 0) setTemplateId(list[0].id);
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      mounted.current = false;
    };
  }, []);

  async function handleCreate() {
    if (!name.trim() || !templateId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const batch = await createNewsBatch({ name, template_id: templateId, item_ids: itemIds });
      onCreated(batch.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo batch thất bại.");
      setBusy(false);
    }
  }

  return (
    <div className="news-modal-backdrop">
      <div className="news-modal" onClick={(e) => e.stopPropagation()}>
        <div className="news-modal-header">
          <h3>Tạo Batch từ {count} tin</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        {error && <div className="news-alert news-alert-error">{error}</div>}
        <label className="news-field">
          <span>Tên batch</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="news-field">
          <span>Template</span>
          <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.builtin ? " (built-in)" : ""}
              </option>
            ))}
          </select>
        </label>
        <p className="news-modal-hint">
          Mỗi tin thành một project (script đã khoá). Sau khi tạo, vào trang Batch bấm "Generate Beats" rồi "Render All".
        </p>
        <div className="news-modal-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Huỷ
          </button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy || !name.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Tạo Batch
          </button>
        </div>
      </div>
    </div>
  );
}
