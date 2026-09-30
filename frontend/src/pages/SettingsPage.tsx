import { useEffect, useState } from "react";
import { CheckCircle2, FolderOpen, LayoutTemplate, Pencil, Plus, Trash2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { FolderBrowserModal } from "../components/FolderBrowserModal";
import { EditTemplateModal } from "../components/EditTemplateModal";
import { CreateTemplateModal } from "../components/CreateTemplateModal";
import {
  getSettings,
  updateAiProvider,
  updateAnthropicApiKey,
  updateLibraryDir,
  updateOpenAiApiKey,
  updateRenderCacheRetention,
} from "../api/settings";
import { deleteTemplate, listTemplates } from "../api/template";
import type { AIProvider } from "../types/settings";
import type { Template } from "../types/videoFactory";
import "./SettingsPage.css";

export function SettingsPage() {
  const [libraryDir, setLibraryDir] = useState<string | null>(null);
  const [showBrowser, setShowBrowser] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dual AI Provider (see docs/features/55-dual-ai-provider.md) -- both
  // keys are always editable regardless of which provider is currently
  // active, so switching back and forth never requires re-entering a key.
  const [aiProvider, setAiProvider] = useState<AIProvider>("anthropic");
  const [savingProvider, setSavingProvider] = useState(false);
  const [hasAnthropicKey, setHasAnthropicKey] = useState(false);
  const [anthropicKeyInput, setAnthropicKeyInput] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [hasOpenAiKey, setHasOpenAiKey] = useState(false);
  const [openAiKeyInput, setOpenAiKeyInput] = useState("");
  const [savingOpenAiKey, setSavingOpenAiKey] = useState(false);

  const [renderCacheDays, setRenderCacheDays] = useState(0);
  const [savingRenderCache, setSavingRenderCache] = useState(false);

  // Video Factory templates (Task 12 -- see docs/features/39-project-templates.md).
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [creatingTemplate, setCreatingTemplate] = useState(false);

  function refreshTemplates() {
    listTemplates()
      .then(setTemplates)
      .catch((err) => setTemplatesError(err instanceof Error ? err.message : "Could not load templates."));
  }

  useEffect(() => {
    getSettings()
      .then((settings) => {
        setLibraryDir(settings.library_dir);
        setAiProvider(settings.ai_provider);
        setHasAnthropicKey(settings.has_anthropic_key);
        setHasOpenAiKey(settings.has_openai_key);
        setRenderCacheDays(settings.render_cache_retention_days);
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

  async function handleSaveOpenAiKey() {
    if (!openAiKeyInput.trim() || savingOpenAiKey) return;
    setSavingOpenAiKey(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateOpenAiApiKey(openAiKeyInput.trim());
      setHasOpenAiKey(result.has_openai_key);
      setOpenAiKeyInput("");
      setMessage("Đã lưu OpenAI API key.");
    } catch {
      setError("Không lưu được API key.");
    } finally {
      setSavingOpenAiKey(false);
    }
  }

  async function handleSaveRenderCache(days: number) {
    if (savingRenderCache || days === renderCacheDays) return;
    setSavingRenderCache(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateRenderCacheRetention(days);
      setRenderCacheDays(result.render_cache_retention_days);
      setMessage(
        days === 0
          ? "Đã tắt tự động dọn render cache."
          : `Đã bật: tự động dọn render cache của video xong sau ${days} ngày.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được cấu hình dọn render cache.");
    } finally {
      setSavingRenderCache(false);
    }
  }

  async function handleChangeProvider(provider: AIProvider) {
    if (provider === aiProvider || savingProvider) return;
    setSavingProvider(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateAiProvider(provider);
      setAiProvider(result.ai_provider);
      setMessage(result.ai_provider === "openai" ? "Đã chuyển sang OpenAI." : "Đã chuyển sang Claude (Anthropic).");
    } catch {
      setError("Không đổi được AI provider.");
    } finally {
      setSavingProvider(false);
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
      <PageHeader title="Settings" subtitle="Cấu hình chung cho lưu trữ, AI và Video Factory" />

      {message && (
        <div className="settings-alert settings-alert-success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}
      {error && <div className="settings-alert settings-alert-error">{error}</div>}

      {/* -- Lưu trữ & dọn dẹp ------------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">Lưu trữ &amp; dọn dẹp</label>
        </div>

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

        <p className="settings-hint">
          Sau khi một video render xong, các file đọc/chuyển động/audio tạm của nó (regenerate được nếu render lại)
          sẽ tự động bị xóa sau số ngày dưới đây, lúc mở app và mỗi 24 giờ. File nhạc bạn tự import và ảnh AI đã sinh
          không bị đụng tới. 0 = tắt.
        </p>
        <div className="settings-row">
          <label className="settings-label" htmlFor="render-cache-days">
            Tự động xóa render cache sau (ngày)
          </label>
          <select
            id="render-cache-days"
            className="settings-input settings-input-narrow"
            value={renderCacheDays}
            disabled={savingRenderCache}
            onChange={(e) => handleSaveRenderCache(Number(e.target.value))}
          >
            <option value={0}>Tắt</option>
            <option value={3}>3 ngày</option>
            <option value={7}>7 ngày</option>
            <option value={14}>14 ngày</option>
            <option value={30}>30 ngày</option>
          </select>
        </div>
      </div>

      {/* -- AI Provider ---------------------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">AI Provider (Content / Beats / AI Story)</label>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="ai-provider">
            Provider đang dùng
          </label>
          <select
            id="ai-provider"
            className="settings-input settings-input-narrow"
            value={aiProvider}
            disabled={savingProvider}
            onChange={(e) => handleChangeProvider(e.target.value as AIProvider)}
          >
            <option value="anthropic">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
          </select>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="anthropic-key">
            Anthropic API Key
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

        <div className="settings-row">
          <label className="settings-label" htmlFor="openai-key">
            OpenAI API Key
          </label>
          <div className="settings-folder-picker">
            <input
              id="openai-key"
              type="password"
              className="settings-input"
              placeholder={hasOpenAiKey ? "•••••••••••••• (đã cấu hình)" : "sk-..."}
              value={openAiKeyInput}
              onChange={(e) => setOpenAiKeyInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveOpenAiKey}
              disabled={!openAiKeyInput.trim() || savingOpenAiKey}
            >
              {hasOpenAiKey && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>
      </div>

      {/* -- Video Factory Templates ----------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">
            <LayoutTemplate size={14} /> Video Factory Templates
          </label>
          <button className="btn btn-secondary" onClick={() => setCreatingTemplate(true)}>
            <Plus size={13} />
            New Template
          </button>
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
                <span className="settings-template-actions">
                  <button className="btn btn-secondary" onClick={() => setEditingTemplate(template)}>
                    <Pencil size={13} />
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDeleteTemplate(template)}
                    disabled={deletingTemplateId === template.id}
                  >
                    <Trash2 size={13} />
                  </button>
                </span>
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

      {editingTemplate && (
        <EditTemplateModal
          template={editingTemplate}
          onSaved={() => {
            setEditingTemplate(null);
            refreshTemplates();
          }}
          onClose={() => setEditingTemplate(null)}
        />
      )}

      {creatingTemplate && (
        <CreateTemplateModal
          existingTemplates={templates}
          onSaved={() => {
            setCreatingTemplate(false);
            refreshTemplates();
          }}
          onClose={() => setCreatingTemplate(false)}
        />
      )}
    </>
  );
}
