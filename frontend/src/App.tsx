import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DownloadPage } from "./pages/DownloadPage";
import { LibraryPage } from "./pages/LibraryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { SceneCutterPage } from "./pages/SceneCutterPage";
import { VideoComposerPage } from "./pages/VideoComposerPage";
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
        <Route path="scene-cutter" element={<SceneCutterPage />} />
        <Route path="video-composer" element={<VideoComposerPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
