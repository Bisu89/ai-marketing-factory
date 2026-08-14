import { useEffect, useState } from "react";
import { CheckCircle2, FolderOpen, LayoutTemplate, Trash2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { FolderBrowserModal } from "../components/FolderBrowserModal";
import { getSettings, updateAnthropicApiKey, updateLibraryDir } from "../api/settings";
import { deleteTemplate, listTemplates } from "../api/template";
import type { Template } from "../types/videoFactory";
import "./SettingsPage.css";

export function SettingsPage() {
  const [libraryDir, setLibraryDir] = useState<string | null>(null);
  const [maxConcurrent, setMaxConcurrent] = useState(3);
  const [defaultQuality, setDefaultQuality] = useState("1080p");
  const [showBrowser, setShowBrowser] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [hasAnthropicKey, setHasAnthropicKey] = useState(false);
  const [anthropicKeyInput, setAnthropicKeyInput] = useState("");
  const [savingKey, setSavingKey] = useState(false);

  // Video Factory templates (Task 12 -- see docs/features/39-project-templates.md).
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null);

  function refreshTemplates() {
    listTemplates()
      .then(setTemplates)
      .catch((err) => setTemplatesError(err instanceof Error ? err.message : "Could not load templates."));
  }

  useEffect(() => {
    getSettings()
      .then((settings) => {
        setLibraryDir(settings.library_dir);
        setHasAnthropicKey(settings.has_anthropic_key);
      })
      .catch(() => setError("Không đọc được cấu hình hiện tại."));
    refreshTemplates();
  }, []);

  async function handleDeleteTemplate(template: Template) {
    if (deletingTemplateId) return;
    if (!window.confirm(`Delete template "${template.name}"? This cannot be undone.`)) return;
    setDeletingTemplateId(template.id);
    setTemplatesError(null);
    try {
      await deleteTemplate(template.id);
      refreshTemplates();
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : "Could not delete template.");
    } finally {
      setDeletingTemplateId(null);
    }
  }

  async function handleSaveAnthropicKey() {
    if (!anthropicKeyInput.trim() || savingKey) return;
    setSavingKey(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateAnthropicApiKey(anthropicKeyInput.trim());
      setHasAnthropicKey(result.has_anthropic_key);
      setAnthropicKeyInput("");
      setMessage("Đã lưu Anthropic API key.");
    } catch {
      setError("Không lưu được API key.");
    } finally {
      setSavingKey(false);
    }
  }

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

        <div className="settings-row">
          <label className="settings-label" htmlFor="anthropic-key">
            Anthropic API Key (dùng cho AI Story)
          </label>
          <div className="settings-folder-picker">
            <input
              id="anthropic-key"
              type="password"
              className="settings-input"
              placeholder={hasAnthropicKey ? "•••••••••••••• (đã cấu hình)" : "sk-ant-..."}
              value={anthropicKeyInput}
              onChange={(e) => setAnthropicKeyInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveAnthropicKey}
              disabled={!anthropicKeyInput.trim() || savingKey}
            >
              {hasAnthropicKey && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">
            <LayoutTemplate size={14} /> Video Factory Templates
          </label>
        </div>
        {templatesError && <div className="settings-alert settings-alert-error">{templatesError}</div>}
        <ul className="settings-template-list">
          {templates.map((template) => (
            <li key={template.id}>
              <span className="settings-template-name">
                {template.name}
                <span className={`settings-template-badge ${template.builtin ? "builtin" : "custom"}`}>
                  {template.builtin ? "Built-in" : "Custom"}
                </span>
              </span>
              <span className="settings-template-desc">{template.description}</span>
              {!template.builtin && (
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDeleteTemplate(template)}
                  disabled={deletingTemplateId === template.id}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </li>
          ))}
        </ul>
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
