import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DownloadPage } from "./pages/DownloadPage";
import { LibraryPage } from "./pages/LibraryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ContentStudioPage } from "./pages/ContentStudioPage";
import { ContentBatchesPage } from "./pages/ContentBatchesPage";
import { ContentBatchDetailPage } from "./pages/ContentBatchDetailPage";
import { WinnerDetectionPage } from "./pages/WinnerDetectionPage";
import { AICostPage } from "./pages/AICostPage";
import { CompetitorIntelligencePage } from "./pages/CompetitorIntelligencePage";
import { AffiliatePage } from "./pages/AffiliatePage";
import { SceneCutterPage } from "./pages/SceneCutterPage";
import { VideoComposerPage } from "./pages/VideoComposerPage";
import { VideoFactoryPage } from "./pages/VideoFactoryPage";
import { VideosPage } from "./pages/VideosPage";
import { BatchPage } from "./pages/BatchPage";
import { BatchDetailPage } from "./pages/BatchDetailPage";
import { SeriesPage } from "./pages/SeriesPage";
import { SeriesDetailPage } from "./pages/SeriesDetailPage";
import { AssetLibraryPage } from "./pages/AssetLibraryPage";
import { SettingsPage } from "./pages/SettingsPage";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="download" element={<DownloadPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="content-studio" element={<ContentStudioPage />} />
        <Route path="content-batches" element={<ContentBatchesPage />} />
        <Route path="content-batches/:batchId" element={<ContentBatchDetailPage />} />
        <Route path="winners" element={<WinnerDetectionPage />} />
        <Route path="ai-costs" element={<AICostPage />} />
        <Route path="competitor-intelligence" element={<CompetitorIntelligencePage />} />
        <Route path="affiliate" element={<AffiliatePage />} />
        <Route path="scene-cutter" element={<SceneCutterPage />} />
        <Route path="video-composer" element={<VideoComposerPage />} />
        <Route path="video-factory" element={<VideoFactoryPage />} />
        <Route path="videos" element={<VideosPage />} />
        <Route path="batches" element={<BatchPage />} />
        <Route path="batches/:batchId" element={<BatchDetailPage />} />
        <Route path="series" element={<SeriesPage />} />
        <Route path="series/:seriesId" element={<SeriesDetailPage />} />
        <Route path="asset-library" element={<AssetLibraryPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
