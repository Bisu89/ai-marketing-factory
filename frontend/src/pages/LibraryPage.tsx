import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Library, Loader2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { ViewToggle } from "../features/library/components/ViewToggle";
import { LibraryFilters } from "../features/library/components/LibraryFilters";
import { VideoGrid } from "../features/library/components/VideoGrid";
import { VideoTable } from "../features/library/components/VideoTable";
import { Pagination } from "../features/library/components/Pagination";
import { VideoDetailDrawer } from "../features/library/components/VideoDetailDrawer";
import { useVideos } from "../features/library/hooks/useVideos";
import { useCategories } from "../features/library/hooks/useCategories";
import { useEmotions } from "../features/library/hooks/useEmotions";
import {
  useAddTags,
  useOpenFolder,
  useRemoveTag,
  useToggleFavorite,
  useUpdateVideo,
} from "../features/library/hooks/useVideoMutations";
import type { VideoListParams, ViewMode } from "../features/library/types";
import "./LibraryPage.css";

const PAGE_SIZE = 24;

function parseFilters(searchParams: URLSearchParams): VideoListParams {
  return {
    page: Number(searchParams.get("page") ?? "1"),
    page_size: PAGE_SIZE,
    sort: searchParams.get("sort") ?? "newest",
    search: searchParams.get("search") ?? undefined,
    platform: searchParams.get("platform") ?? undefined,
    status: searchParams.get("status") ?? undefined,
    category_id: searchParams.get("category_id") ? Number(searchParams.get("category_id")) : undefined,
    emotion_id: searchParams.get("emotion_id") ? Number(searchParams.get("emotion_id")) : undefined,
    favorite: searchParams.get("favorite") === "true" ? true : undefined,
    duration: searchParams.get("duration") ?? undefined,
    resolution: searchParams.get("resolution") ?? undefined,
  };
}

export function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const view = (searchParams.get("view") as ViewMode) || "grid";
  const filters = parseFilters(searchParams);

  const videosQuery = useVideos(filters);
  const categoriesQuery = useCategories();
  const emotionsQuery = useEmotions();
  const toggleFavorite = useToggleFavorite();
  const openFolder = useOpenFolder();
  const updateVideo = useUpdateVideo();
  const addTags = useAddTags();
  const removeTag = useRemoveTag();

  function setView(next: ViewMode) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", next);
      return params;
    });
  }

  function setPage(next: number) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("page", String(next));
      return params;
    });
  }

  function updateFilters(patch: Partial<VideoListParams>) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined || value === "" || value === null) {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      // Any filter change invalidates the current page of results.
      params.delete("page");
      return params;
    });
  }

  function handleToggleFavorite(videoId: number, favorite: boolean) {
    setActionError(null);
    toggleFavorite.mutate(
      { videoId, favorite },
      { onError: (err) => setActionError(err instanceof Error ? err.message : "Failed to update favorite") },
    );
  }

  function handleOpenFolder(videoId: number) {
    setActionError(null);
    openFolder.mutate(videoId, {
      onError: (err) => setActionError(err instanceof Error ? err.message : "Failed to open folder"),
    });
  }

  function handleUpdateVideo(
    videoId: number,
    patch: { status?: string; category_id?: number; emotion_id?: number; notes?: string },
  ) {
    setActionError(null);
    updateVideo.mutate(
      { videoId, patch },
      { onError: (err) => setActionError(err instanceof Error ? err.message : "Không cập nhật được video") },
    );
  }

  function handleAddTags(videoId: number, tagNames: string[]) {
    setActionError(null);
    addTags.mutate(
      { videoId, tagNames },
      { onError: (err) => setActionError(err instanceof Error ? err.message : "Không thêm được tag") },
    );
  }

  function handleRemoveTag(videoId: number, tagId: number) {
    setActionError(null);
    removeTag.mutate(
      { videoId, tagId },
      { onError: (err) => setActionError(err instanceof Error ? err.message : "Không xoá được tag") },
    );
  }

  const videos = videosQuery.data?.items ?? [];
  const categories = categoriesQuery.data ?? [];
  const emotions = emotionsQuery.data ?? [];
  const selectedVideo = videos.find((v) => v.id === selectedVideoId) ?? null;

  return (
    <>
      <PageHeader
        title="Library"
        subtitle="Toàn bộ video đã tải về, có thể tìm kiếm và lọc"
        actions={<ViewToggle value={view} onChange={setView} />}
      />

      <LibraryFilters filters={filters} categories={categories} emotions={emotions} onChange={updateFilters} />

      {actionError && <div className="library-error">{actionError}</div>}

      {videosQuery.isLoading ? (
        <div className="library-loading">
          <Loader2 size={20} className="spin" /> Đang tải...
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={Library}
          title="Không tìm thấy video nào"
          description="Thử bỏ bớt bộ lọc, hoặc tải video mới từ trang Download."
        />
      ) : (
        <>
          {view === "grid" ? (
            <VideoGrid
              videos={videos}
              onToggleFavorite={handleToggleFavorite}
              onOpenFolder={handleOpenFolder}
              onPreview={setSelectedVideoId}
            />
          ) : (
            <VideoTable
              videos={videos}
              onToggleFavorite={handleToggleFavorite}
              onOpenFolder={handleOpenFolder}
              onPreview={setSelectedVideoId}
            />
          )}

          <Pagination page={filters.page} pageSize={PAGE_SIZE} total={videosQuery.data?.total ?? 0} onChange={setPage} />
        </>
      )}

      {selectedVideo && (
        <VideoDetailDrawer
          video={selectedVideo}
          categories={categories}
          emotions={emotions}
          onClose={() => setSelectedVideoId(null)}
          onToggleFavorite={() => handleToggleFavorite(selectedVideo.id, !selectedVideo.is_favorite)}
          onOpenFolder={() => handleOpenFolder(selectedVideo.id)}
          onUpdate={(patch) => handleUpdateVideo(selectedVideo.id, patch)}
          onAddTags={(tagNames) => handleAddTags(selectedVideo.id, tagNames)}
          onRemoveTag={(tagId) => handleRemoveTag(selectedVideo.id, tagId)}
        />
      )}
    </>
  );
}
