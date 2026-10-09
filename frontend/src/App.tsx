import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DownloadPage } from "./pages/DownloadPage";
import { StorytellerPage } from "./pages/StorytellerPage";
import { LibraryPage } from "./pages/LibraryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { StudioPage } from "./pages/StudioPage";
import { StudioStoryPage } from "./pages/StudioStoryPage";
import { AICostPage } from "./pages/AICostPage";
import { VideoComposerPage } from "./pages/VideoComposerPage";
import { VideoFactoryPage } from "./pages/VideoFactoryPage";
import { VideosPage } from "./pages/VideosPage";
import { AssetLibraryPage } from "./pages/AssetLibraryPage";
import { ManhuaFetchPage } from "./pages/ManhuaFetchPage";
import { VoiceTestPage } from "./pages/VoiceTestPage";
import { SettingsPage } from "./pages/SettingsPage";
import { DocumentaryListPage } from "./pages/DocumentaryListPage";
import { DocumentaryProjectPage } from "./pages/DocumentaryProjectPage";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="download" element={<DownloadPage />} />
        <Route path="storyteller" element={<StorytellerPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="studio" element={<StudioPage />} />
        <Route path="studio/:storyId" element={<StudioStoryPage />} />
        <Route path="ai-costs" element={<AICostPage />} />
        <Route path="video-composer" element={<VideoComposerPage />} />
        <Route path="video-factory" element={<VideoFactoryPage />} />
        <Route path="videos" element={<VideosPage />} />
        <Route path="asset-library" element={<AssetLibraryPage />} />
        <Route path="manhua-fetch" element={<ManhuaFetchPage />} />
        <Route path="voice-test" element={<VoiceTestPage />} />
        <Route path="documentary" element={<DocumentaryListPage />} />
        <Route path="documentary/:id" element={<DocumentaryProjectPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
