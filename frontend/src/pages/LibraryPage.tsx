import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Library, Loader2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { ViewToggle } from "../features/library/components/ViewToggle";
import { VideoGrid } from "../features/library/components/VideoGrid";
import { VideoTable } from "../features/library/components/VideoTable";
import { Pagination } from "../features/library/components/Pagination";
import { VideoDetailDrawer } from "../features/library/components/VideoDetailDrawer";
import { useVideos } from "../features/library/hooks/useVideos";
import { useCategories } from "../features/library/hooks/useCategories";
import { useOpenFolder, useToggleFavorite } from "../features/library/hooks/useVideoMutations";
import type { ViewMode } from "../features/library/types";
import "./LibraryPage.css";

const PAGE_SIZE = 24;

export function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const view = (searchParams.get("view") as ViewMode) || "grid";
  const page = Number(searchParams.get("page") ?? "1");

  const videosQuery = useVideos({ page, page_size: PAGE_SIZE, sort: "newest" });
  const categoriesQuery = useCategories();
  const toggleFavorite = useToggleFavorite();
  const openFolder = useOpenFolder();

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

  const videos = videosQuery.data?.items ?? [];
  const categories = categoriesQuery.data ?? [];
  const selectedVideo = videos.find((v) => v.id === selectedVideoId) ?? null;

  return (
    <>
      <PageHeader
        title="Library"
        subtitle="Toàn bộ video đã tải về, có thể tìm kiếm và lọc"
        actions={<ViewToggle value={view} onChange={setView} />}
      />

      {actionError && <div className="library-error">{actionError}</div>}

      {videosQuery.isLoading ? (
        <div className="library-loading">
          <Loader2 size={20} className="spin" /> Đang tải...
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={Library}
          title="Thư viện đang trống"
          description="Video sau khi tải xong từ trang Download sẽ xuất hiện ở đây."
        />
      ) : (
        <>
          {view === "grid" ? (
            <VideoGrid
              videos={videos}
              categories={categories}
              onToggleFavorite={handleToggleFavorite}
              onOpenFolder={handleOpenFolder}
              onPreview={setSelectedVideoId}
            />
          ) : (
            <VideoTable
              videos={videos}
              categories={categories}
              onToggleFavorite={handleToggleFavorite}
              onOpenFolder={handleOpenFolder}
              onPreview={setSelectedVideoId}
            />
          )}

          <Pagination page={page} pageSize={PAGE_SIZE} total={videosQuery.data?.total ?? 0} onChange={setPage} />
        </>
      )}

      {selectedVideo && (
        <VideoDetailDrawer
          video={selectedVideo}
          categories={categories}
          onClose={() => setSelectedVideoId(null)}
          onToggleFavorite={() => handleToggleFavorite(selectedVideo.id, !selectedVideo.is_favorite)}
          onOpenFolder={() => handleOpenFolder(selectedVideo.id)}
        />
      )}
    </>
  );
}
