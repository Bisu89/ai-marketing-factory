import { useEffect, useState } from "react";
import { CheckCircle2, FolderOpen } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { FolderBrowserModal } from "../components/FolderBrowserModal";
import { getSettings, updateLibraryDir } from "../api/settings";
import "./SettingsPage.css";

export function SettingsPage() {
  const [libraryDir, setLibraryDir] = useState<string | null>(null);
  const [maxConcurrent, setMaxConcurrent] = useState(3);
  const [defaultQuality, setDefaultQuality] = useState("1080p");
  const [showBrowser, setShowBrowser] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSettings()
      .then((settings) => setLibraryDir(settings.library_dir))
      .catch(() => setError("Không đọc được cấu hình hiện tại."));
  }, []);

  async function handleSelectFolder(path: string) {
    setShowBrowser(false);
    setError(null);
    setMessage(null);
    try {
      const result = await updateLibraryDir(path);
      setLibraryDir(result.library_dir);
      setMessage("Đã đổi thư mục lưu trữ. Các lượt tải mới sẽ lưu vào đây.");
    } catch {
      setError("Không đổi được thư mục lưu trữ.");
    }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Cấu hình chung cho việc tải và lưu trữ" />

      {message && (
        <div className="settings-alert settings-alert-success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}
      {error && <div className="settings-alert settings-alert-error">{error}</div>}

      <div className="settings-card">
        <div className="settings-row">
          <label className="settings-label">Thư mục lưu trữ</label>
          <div className="settings-folder-picker">
            <span className="settings-path">{libraryDir ?? "Đang tải..."}</span>
            <button className="btn btn-secondary" onClick={() => setShowBrowser(true)}>
              <FolderOpen size={14} />
              Đổi thư mục...
            </button>
          </div>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="max-concurrent">
            Số lượt tải song song tối đa
          </label>
          <input
            id="max-concurrent"
            type="number"
            min={1}
            max={10}
            className="settings-input settings-input-narrow"
            value={maxConcurrent}
            onChange={(e) => setMaxConcurrent(Number(e.target.value))}
          />
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="default-quality">
            Chất lượng mặc định
          </label>
          <select
            id="default-quality"
            className="settings-input settings-input-narrow"
            value={defaultQuality}
            onChange={(e) => setDefaultQuality(e.target.value)}
          >
            <option value="2160p">2160p (4K)</option>
            <option value="1080p">1080p</option>
            <option value="720p">720p</option>
            <option value="480p">480p</option>
          </select>
        </div>
      </div>

      {showBrowser && (
        <FolderBrowserModal
          initialPath={libraryDir ?? undefined}
          onSelect={handleSelectFolder}
          onClose={() => setShowBrowser(false)}
        />
      )}
    </>
  );
}
