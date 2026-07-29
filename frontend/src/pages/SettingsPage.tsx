import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import "./SettingsPage.css";

export function SettingsPage() {
  const [storagePath, setStoragePath] = useState("C:\\Users\\Public\\AIContentLibrary\\media");
  const [maxConcurrent, setMaxConcurrent] = useState(3);
  const [defaultQuality, setDefaultQuality] = useState("1080p");

  return (
    <>
      <PageHeader title="Settings" subtitle="Cấu hình chung cho việc tải và lưu trữ" />

      <div className="settings-card">
        <div className="settings-row">
          <label className="settings-label" htmlFor="storage-path">
            Thư mục lưu trữ
          </label>
          <input
            id="storage-path"
            className="settings-input"
            value={storagePath}
            onChange={(e) => setStoragePath(e.target.value)}
          />
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
    </>
  );
}
