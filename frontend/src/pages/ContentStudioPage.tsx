import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Layers, Loader2, Sparkles, TrendingDown, TrendingUp, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../features/library/components/Pagination";
import { useEmotions } from "../features/library/hooks/useEmotions";
import { createIdea } from "../api/contentStrategy";
import { createContentBatch, runContentBatch } from "../api/contentBatch";
import { getContentRecommendations } from "../api/recommendation";
import { fetchVideos } from "../api/videos";
import type { Recommendation } from "../types/recommendation";
import { IdeaCard } from "../features/contentStudio/components/IdeaCard";
import { useAllContentFormats } from "../features/contentStudio/hooks/useAllContentFormats";
import { useContentFormats } from "../features/contentStudio/hooks/useContentFormats";
import { useContentIdeas } from "../features/contentStudio/hooks/useContentIdeas";
import { useContentPillars } from "../features/contentStudio/hooks/useContentPillars";
import { useDeleteIdea, useUpdateIdea } from "../features/contentStudio/hooks/useIdeaMutations";
import type { IdeaStatus, IdeaUpdateInput } from "../features/contentStudio/types";
import { STORY_STYLE_LABELS, type StoryStyle } from "../types/publishLog";
import type { VideoOut } from "../features/library/types";
import "./ContentStudioPage.css";

const PAGE_SIZE = 12;

const STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Nháp",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  used: "Đã dùng",
};

const STORY_STYLES = Object.keys(STORY_STYLE_LABELS) as StoryStyle[];

const BATCH_LANGUAGE_LABELS: Record<string, string> = {
  english: "Tiếng Anh",
  spanish: "Tiếng Tây Ban Nha",
  vietnamese: "Tiếng Việt",
};

export function ContentStudioPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // -- Strategy selector (generate) ---------------------------------------
  const [genPillarId, setGenPillarId] = useState<number | undefined>(undefined);
  const [genFormatId, setGenFormatId] = useState<number | undefined>(undefined);
  const [ideaCount, setIdeaCount] = useState(3);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // -- Review: filters + pagination + selection ---------------------------
  const [filterPillarId, setFilterPillarId] = useState<number | undefined>(undefined);
  const [filterFormatId, setFilterFormatId] = useState<number | undefined>(undefined);
  const [filterStatus, setFilterStatus] = useState<IdeaStatus | undefined>(undefined);
  const [minScoreText, setMinScoreText] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [batchModalOpen, setBatchModalOpen] = useState(false);

  // AI Content Recommendations (Task 09) -- display-only advice, fetched
  // once and never used to auto-fill/auto-trigger anything below; the
  // user reads it, then still picks Pillar/Format/count themselves.
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState(true);

  useEffect(() => {
    getContentRecommendations()
      .then(setRecommendations)
      .catch((err) => setRecommendationsError(err instanceof Error ? err.message : "Không tải được gợi ý."))
      .finally(() => setRecommendationsLoading(false));
  }, []);

  const pillarsQuery = useContentPillars();
  const allFormatsQuery = useAllContentFormats();
  const genFormatsQuery = useContentFormats(genPillarId);
  const filterFormatsQuery = useContentFormats(filterPillarId);

  const minScore = minScoreText.trim() === "" ? undefined : Number(minScoreText);
  const ideasQuery = useContentIdeas({
    pillar_id: filterPillarId,
    format_id: filterFormatId,
    status: filterStatus,
    min_score: minScore,
    page,
    page_size: PAGE_SIZE,
  });

  const updateIdea = useUpdateIdea();
  const deleteIdea = useDeleteIdea();

  // Selection doesn't survive a filter/page change -- the set of visible
  // ideas changed, so a stale selection would silently apply bulk actions
  // to ideas the user can no longer see.
  useEffect(() => {
    setSelectedIds(new Set());
  }, [filterPillarId, filterFormatId, filterStatus, minScore, page]);

  const pillarNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const p of pillarsQuery.data ?? []) map.set(p.id, p.name);
    return map;
  }, [pillarsQuery.data]);

  const formatNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const f of allFormatsQuery.data ?? []) map.set(f.id, f.name);
    return map;
  }, [allFormatsQuery.data]);

  async function handleGenerate() {
    if (!genPillarId || !genFormatId || ideaCount < 1 || generating) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      for (let i = 1; i <= ideaCount; i++) {
        await createIdea({
          pillar_id: genPillarId,
          format_id: genFormatId,
          title: `Ý tưởng mới #${i}`,
          status: "draft",
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
      // Jump the review filters to what was just generated so the new
      // drafts are immediately visible, not buried under old ones.
      setFilterPillarId(genPillarId);
      setFilterFormatId(genFormatId);
      setFilterStatus(undefined);
      setPage(1);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Không tạo được ý tưởng.");
    } finally {
      setGenerating(false);
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleBulkStatus(status: IdeaStatus) {
    if (selectedIds.size === 0 || bulkBusy) return;
    setBulkBusy(true);
    setBulkError(null);
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => updateIdea.mutateAsync({ ideaId: id, patch: { status } })),
      );
      setSelectedIds(new Set());
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : "Không cập nhật được trạng thái đã chọn.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function handleSaveIdea(id: number, patch: IdeaUpdateInput) {
    await updateIdea.mutateAsync({ ideaId: id, patch });
  }

  async function handleDeleteIdea(id: number) {
    setDeletingId(id);
    try {
      await deleteIdea.mutateAsync(id);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } finally {
      setDeletingId(null);
    }
  }

  const ideas = ideasQuery.data?.items ?? [];
  const total = ideasQuery.data?.total ?? 0;
  const emotionsQuery = useEmotions();

  return (
    <>
      <PageHeader
        title="Content Studio"
        subtitle="Pillar → Format → số lượng ý tưởng → tạo → duyệt → chọn ý tưởng để đưa vào sản xuất."
      />

      <section className="cs-section">
        <h2 className="cs-section-title">AI Content Recommendations</h2>
        <p className="cs-hint cs-hint-top">
          Gợi ý dựa trên hiệu suất lịch sử thật (Winner Detection) -- chỉ mang tính tham khảo, không tự động áp dụng.
          Bạn vẫn tự chọn Pillar/Format ở dưới như bình thường.
        </p>
        {recommendationsError && <div className="cs-alert cs-alert-error">{recommendationsError}</div>}
        {recommendationsLoading ? (
          <div className="cs-loading">
            <Loader2 size={18} className="spin" />
          </div>
        ) : recommendations.length === 0 ? (
          <p className="cs-hint">
            Chưa đủ dữ liệu hiệu suất (video đã đăng + gắn Insights) để đưa ra gợi ý nào.
          </p>
        ) : (
          <div className="cs-recommendation-list">
            {recommendations.map((rec) => (
              <div key={`${rec.dimension}-${rec.label}`} className="cs-recommendation-card">
                <div className="cs-recommendation-top">
                  {rec.trend === "rising" ? (
                    <TrendingUp size={14} className="cs-recommendation-trend-up" />
                  ) : rec.trend === "underperforming" ? (
                    <TrendingDown size={14} className="cs-recommendation-trend-down" />
                  ) : null}
                  <strong>{rec.label}</strong>
                  <span className="cs-recommendation-dimension">{rec.dimension}</span>
                  <span className="cs-recommendation-weight">{rec.weight.toFixed(2)}</span>
                </div>
                <ul className="cs-recommendation-reasons">
                  {rec.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="cs-section">
        <h2 className="cs-section-title">Tạo ý tưởng</h2>
        <div className="cs-generate-bar">
          <label className="cs-field">
            <span>Pillar</span>
            <select
              value={genPillarId ?? ""}
              onChange={(e) => {
                const value = e.target.value ? Number(e.target.value) : undefined;
                setGenPillarId(value);
                setGenFormatId(undefined);
              }}
            >
              <option value="">— Chọn pillar —</option>
              {(pillarsQuery.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label className="cs-field">
            <span>Format</span>
            <select
              value={genFormatId ?? ""}
              onChange={(e) => setGenFormatId(e.target.value ? Number(e.target.value) : undefined)}
              disabled={!genPillarId}
            >
              <option value="">— Chọn format —</option>
              {(genFormatsQuery.data ?? []).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>

          <label className="cs-field cs-field-narrow">
            <span>Số lượng ý tưởng</span>
            <input
              type="number"
              min={1}
              max={20}
              value={ideaCount}
              onChange={(e) => setIdeaCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            />
          </label>

          <button
            className="btn btn-primary cs-generate-btn"
            onClick={handleGenerate}
            disabled={!genPillarId || !genFormatId || generating}
          >
            {generating ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            Tạo ý tưởng
          </button>
        </div>

        {genPillarId && !genFormatsQuery.isLoading && (genFormatsQuery.data?.length ?? 0) === 0 && (
          <p className="cs-hint">
            Pillar này chưa có Format nào. Cần khởi tạo Format trước khi tạo ý tưởng (chưa có màn quản lý Format).
          </p>
        )}

        <p className="cs-hint">
          AI chưa được tích hợp ở bước này: mỗi lần bấm "Tạo ý tưởng" sẽ tạo ra {ideaCount} ý tưởng nháp trống theo
          Pillar/Format đã chọn, để bạn tự nhập tiêu đề/premise ở khu vực Duyệt ý tưởng bên dưới.
        </p>

        {generateError && <div className="cs-alert cs-alert-error">{generateError}</div>}
      </section>

      <section className="cs-section">
        <h2 className="cs-section-title">Duyệt ý tưởng</h2>

        <div className="cs-filter-bar">
          <label className="cs-field">
            <span>Pillar</span>
            <select
              value={filterPillarId ?? ""}
              onChange={(e) => {
                const value = e.target.value ? Number(e.target.value) : undefined;
                setFilterPillarId(value);
                setFilterFormatId(undefined);
                setPage(1);
              }}
            >
              <option value="">Tất cả</option>
              {(pillarsQuery.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label className="cs-field">
            <span>Format</span>
            <select
              value={filterFormatId ?? ""}
              onChange={(e) => {
                setFilterFormatId(e.target.value ? Number(e.target.value) : undefined);
                setPage(1);
              }}
              disabled={!filterPillarId}
            >
              <option value="">Tất cả</option>
              {(filterFormatsQuery.data ?? []).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>

          <label className="cs-field">
            <span>Trạng thái</span>
            <select
              value={filterStatus ?? ""}
              onChange={(e) => {
                setFilterStatus((e.target.value || undefined) as IdeaStatus | undefined);
                setPage(1);
              }}
            >
              <option value="">Tất cả</option>
              {(Object.keys(STATUS_LABELS) as IdeaStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </label>

          <label className="cs-field cs-field-narrow">
            <span>Điểm tối thiểu</span>
            <input
              type="number"
              step="0.1"
              value={minScoreText}
              onChange={(e) => {
                setMinScoreText(e.target.value);
                setPage(1);
              }}
              placeholder="—"
            />
          </label>
        </div>

        {selectedIds.size > 0 && (
          <div className="cs-bulk-bar">
            <span>Đã chọn {selectedIds.size} ý tưởng</span>
            <div className="cs-bulk-actions">
              <button className="btn btn-secondary" disabled={bulkBusy} onClick={() => handleBulkStatus("approved")}>
                Duyệt
              </button>
              <button className="btn btn-secondary" disabled={bulkBusy} onClick={() => handleBulkStatus("rejected")}>
                Từ chối
              </button>
              <button className="btn btn-secondary" disabled={bulkBusy} onClick={() => handleBulkStatus("used")}>
                Đánh dấu đã dùng
              </button>
              <button className="btn btn-primary" disabled={bulkBusy} onClick={() => setBatchModalOpen(true)}>
                <Layers size={13} />
                Tạo Story hàng loạt
              </button>
            </div>
          </div>
        )}
        {bulkError && <div className="cs-alert cs-alert-error">{bulkError}</div>}

        {ideasQuery.isLoading ? (
          <div className="cs-loading">
            <Loader2 size={20} className="spin" />
          </div>
        ) : ideasQuery.isError ? (
          <div className="cs-alert cs-alert-error">
            {ideasQuery.error instanceof Error ? ideasQuery.error.message : "Không tải được danh sách ý tưởng."}
          </div>
        ) : ideas.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="Chưa có ý tưởng nào"
            description="Chọn Pillar và Format ở trên rồi bấm Tạo ý tưởng, hoặc nới lỏng bộ lọc bên dưới."
          />
        ) : (
          <>
            <div className="cs-idea-list">
              {ideas.map((idea) => (
                <IdeaCard
                  key={idea.id}
                  idea={idea}
                  pillarName={pillarNameById.get(idea.pillar_id) ?? `#${idea.pillar_id}`}
                  formatName={formatNameById.get(idea.format_id) ?? `#${idea.format_id}`}
                  emotions={emotionsQuery.data ?? []}
                  selected={selectedIds.has(idea.id)}
                  onToggleSelect={toggleSelect}
                  onSave={handleSaveIdea}
                  onDelete={handleDeleteIdea}
                  deleting={deletingId === idea.id}
                />
              ))}
            </div>
            <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} itemLabel="ý tưởng" />
          </>
        )}
      </section>

      {batchModalOpen && (
        <CreateContentBatchModal
          ideaIds={Array.from(selectedIds)}
          onClose={() => setBatchModalOpen(false)}
          onCreated={(batchId) => {
            setBatchModalOpen(false);
            navigate(`/content-batches/${batchId}`);
          }}
        />
      )}
    </>
  );
}

function CreateContentBatchModal({
  ideaIds,
  onClose,
  onCreated,
}: {
  ideaIds: number[];
  onClose: () => void;
  onCreated: (batchId: number) => void;
}) {
  const [name, setName] = useState(`Batch ${new Date().toLocaleDateString("vi-VN")}`);
  const [videos, setVideos] = useState<VideoOut[]>([]);
  const [videosError, setVideosError] = useState<string | null>(null);
  const [videoId, setVideoId] = useState<number | "">("");
  const [style, setStyle] = useState<StoryStyle>("emotional");
  const [language, setLanguage] = useState("english");
  const [threshold, setThreshold] = useState(8.0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVideos({ page: 1, page_size: 50, sort: "newest" })
      .then((res) => {
        setVideos(res.items);
        if (res.items.length > 0) setVideoId(res.items[0].id);
      })
      .catch((err) => setVideosError(err instanceof Error ? err.message : "Không tải được danh sách video."));
  }, []);

  async function handleSubmit() {
    if (!name.trim() || !videoId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const batch = await createContentBatch({
        name: name.trim(),
        video_id: Number(videoId),
        idea_ids: ideaIds,
        style,
        language,
        score_threshold: threshold,
      });
      await runContentBatch(batch.id);
      onCreated(batch.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạo được batch.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="cs-modal-backdrop" onClick={onClose}>
      <div className="cs-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cs-modal-header">
          <h3>Tạo Story hàng loạt ({ideaIds.length} ý tưởng)</h3>
          <button className="btn btn-secondary" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="cs-alert cs-alert-error">{error}</div>}

        <label className="cs-field">
          <span>Tên batch</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <label className="cs-field">
          <span>Video (mọi story trong batch sẽ gắn với video này)</span>
          {videosError ? (
            <span className="cs-field-error">{videosError}</span>
          ) : (
            <select value={videoId} onChange={(e) => setVideoId(e.target.value ? Number(e.target.value) : "")}>
              {videos.length === 0 && <option value="">Chưa có video nào trong Library</option>}
              {videos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.title}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="cs-field">
          <span>Style</span>
          <select value={style} onChange={(e) => setStyle(e.target.value as StoryStyle)}>
            {STORY_STYLES.map((s) => (
              <option key={s} value={s}>
                {STORY_STYLE_LABELS[s]}
              </option>
            ))}
          </select>
        </label>

        <label className="cs-field">
          <span>Ngôn ngữ</span>
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            {Object.entries(BATCH_LANGUAGE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="cs-field">
          <span>Ngưỡng điểm đạt ({threshold.toFixed(1)}/10)</span>
          <input
            type="number"
            min={0}
            max={10}
            step={0.5}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          />
        </label>

        <p className="cs-hint">
          Mỗi ý tưởng sẽ được sinh 1 story rồi chấm điểm tự động. Story đạt từ ngưỡng trở lên sẽ được đánh dấu "Đạt",
          dưới ngưỡng bị đánh dấu "Không đạt" — không có gì bị xoá, bạn xem lại được toàn bộ ở trang chi tiết batch.
        </p>

        <div className="cs-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Huỷ
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting || !videoId}>
            {submitting ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            Tạo và chạy batch
          </button>
        </div>
      </div>
    </div>
  );
}
