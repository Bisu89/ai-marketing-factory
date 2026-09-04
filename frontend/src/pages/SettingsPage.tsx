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
  updateDefaultVoice,
  updateLibraryDir,
  updateOpenAiApiKey,
  updateNewsPollInterval,
  updateRenderCacheRetention,
  updateGoogleOAuthClient,
  updateTikTokClientKey,
  updateTikTokClientSecret,
  updateTikTokRedirectUri,
} from "../api/settings";
import { listLocalVoices } from "../api/voice";
import type { LocalVoiceOption } from "../api/voice";
import { deleteTemplate, listTemplates } from "../api/template";
import type { AIProvider } from "../types/settings";
import type { Template } from "../types/videoFactory";
import { VOICE_OPTIONS } from "../types/videoFactory";
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

  // Competitor Content Analyzer (Task 11 -- see
  // docs/features/76-competitor-content-analyzer.md). A TikTok Developer
  // app (client key/secret + an HTTPS redirect URI *you* register with
  // TikTok) is a real setup requirement -- this app cannot create or
  // approve one for you.
  const [hasTikTokClientKey, setHasTikTokClientKey] = useState(false);
  const [tiktokClientKeyInput, setTiktokClientKeyInput] = useState("");
  const [savingTikTokClientKey, setSavingTikTokClientKey] = useState(false);
  const [hasTikTokClientSecret, setHasTikTokClientSecret] = useState(false);
  const [tiktokClientSecretInput, setTiktokClientSecretInput] = useState("");
  const [savingTikTokClientSecret, setSavingTikTokClientSecret] = useState(false);
  const [tiktokRedirectUri, setTiktokRedirectUri] = useState<string | null>(null);
  const [tiktokRedirectUriInput, setTiktokRedirectUriInput] = useState("");
  const [savingTikTokRedirectUri, setSavingTikTokRedirectUri] = useState(false);
  const [hasGoogleOAuth, setHasGoogleOAuth] = useState(false);
  const [youtubeRedirectUri, setYoutubeRedirectUri] = useState("");
  const [googleClientIdInput, setGoogleClientIdInput] = useState("");
  const [googleClientSecretInput, setGoogleClientSecretInput] = useState("");
  const [savingGoogleOAuth, setSavingGoogleOAuth] = useState(false);

  const [renderCacheDays, setRenderCacheDays] = useState(0);
  const [savingRenderCache, setSavingRenderCache] = useState(false);
  const [newsPollMinutes, setNewsPollMinutes] = useState(0);
  const [savingNewsPoll, setSavingNewsPoll] = useState(false);

  // Default narration settings -- pre-fill a NEW template's voice fields
  // (CreateTemplateModal, "Blank" start). Never touches an existing
  // template or project.
  const [defaultVoiceProvider, setDefaultVoiceProvider] = useState<"local" | "edge_tts">("local");
  const [defaultVoiceId, setDefaultVoiceId] = useState("default");
  const [defaultVoiceSpeed, setDefaultVoiceSpeed] = useState(1.0);
  const [defaultSentencePause, setDefaultSentencePause] = useState(0.35);
  const [savingDefaultVoice, setSavingDefaultVoice] = useState(false);
  const [localVoices, setLocalVoices] = useState<LocalVoiceOption[]>([]);

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
        setHasTikTokClientKey(settings.has_tiktok_client_key);
        setHasTikTokClientSecret(settings.has_tiktok_client_secret);
        setTiktokRedirectUri(settings.tiktok_redirect_uri);
        setHasGoogleOAuth(settings.has_google_oauth_client);
        setYoutubeRedirectUri(settings.youtube_redirect_uri);
        setRenderCacheDays(settings.render_cache_retention_days);
        setNewsPollMinutes(settings.news_poll_interval_minutes);
        // Fall back to the built-in defaults if the backend predates this
        // feature (GET /settings without the default_voice_* keys).
        setDefaultVoiceProvider(settings.default_voice_provider ?? "local");
        setDefaultVoiceId(settings.default_voice_id ?? "default");
        setDefaultVoiceSpeed(settings.default_voice_speed ?? 1.0);
        setDefaultSentencePause(settings.default_sentence_pause_sec ?? 0.35);
      })
      .catch(() => setError("Không đọc được cấu hình hiện tại."));
    refreshTemplates();
    listLocalVoices().then(setLocalVoices).catch(() => setLocalVoices([]));
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

  async function handleSaveTikTokClientKey() {
    if (!tiktokClientKeyInput.trim() || savingTikTokClientKey) return;
    setSavingTikTokClientKey(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateTikTokClientKey(tiktokClientKeyInput.trim());
      setHasTikTokClientKey(result.has_tiktok_client_key);
      setTiktokClientKeyInput("");
      setMessage("Đã lưu TikTok Client Key.");
    } catch {
      setError("Không lưu được TikTok Client Key.");
    } finally {
      setSavingTikTokClientKey(false);
    }
  }

  async function handleSaveTikTokClientSecret() {
    if (!tiktokClientSecretInput.trim() || savingTikTokClientSecret) return;
    setSavingTikTokClientSecret(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateTikTokClientSecret(tiktokClientSecretInput.trim());
      setHasTikTokClientSecret(result.has_tiktok_client_secret);
      setTiktokClientSecretInput("");
      setMessage("Đã lưu TikTok Client Secret.");
    } catch {
      setError("Không lưu được TikTok Client Secret.");
    } finally {
      setSavingTikTokClientSecret(false);
    }
  }

  async function handleSaveTikTokRedirectUri() {
    if (!tiktokRedirectUriInput.trim() || savingTikTokRedirectUri) return;
    setSavingTikTokRedirectUri(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateTikTokRedirectUri(tiktokRedirectUriInput.trim());
      setTiktokRedirectUri(result.tiktok_redirect_uri);
      setTiktokRedirectUriInput("");
      setMessage("Đã lưu TikTok Redirect URI.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được TikTok Redirect URI.");
    } finally {
      setSavingTikTokRedirectUri(false);
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

  async function handleSaveGoogleOAuth() {
    if (!googleClientIdInput.trim() || !googleClientSecretInput.trim() || savingGoogleOAuth) return;
    setSavingGoogleOAuth(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateGoogleOAuthClient(googleClientIdInput.trim(), googleClientSecretInput.trim());
      setHasGoogleOAuth(result.has_google_oauth_client);
      setGoogleClientIdInput("");
      setGoogleClientSecretInput("");
      setMessage("Đã lưu Google OAuth client. Sang trang Publishing để kết nối kênh.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được Google OAuth client.");
    } finally {
      setSavingGoogleOAuth(false);
    }
  }

  async function handleSaveNewsPoll(minutes: number) {
    if (savingNewsPoll || minutes === newsPollMinutes) return;
    setSavingNewsPoll(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateNewsPollInterval(minutes);
      setNewsPollMinutes(result.news_poll_interval_minutes);
      setMessage(
        minutes === 0
          ? "Đã tắt tự động kéo tin RSS."
          : `Đã bật: tự động kéo tin RSS mỗi ${minutes} phút.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được cấu hình kéo tin.");
    } finally {
      setSavingNewsPoll(false);
    }
  }

  async function handleSaveDefaultVoice() {
    if (savingDefaultVoice) return;
    setSavingDefaultVoice(true);
    setError(null);
    setMessage(null);
    try {
      const result = await updateDefaultVoice({
        provider: defaultVoiceProvider,
        voice_id: defaultVoiceId,
        speed: defaultVoiceSpeed,
        sentence_pause_sec: defaultSentencePause,
      });
      setDefaultVoiceProvider(result.default_voice_provider);
      setDefaultVoiceId(result.default_voice_id);
      setDefaultVoiceSpeed(result.default_voice_speed);
      setDefaultSentencePause(result.default_sentence_pause_sec);
      setMessage("Đã lưu giọng đọc mặc định. Áp dụng khi bạn tạo Template mới từ 'Blank'.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được giọng đọc mặc định.");
    } finally {
      setSavingDefaultVoice(false);
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

      {/* -- Giọng đọc mặc định ------------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">Giọng đọc mặc định (cho Template mới)</label>
        </div>
        <p className="settings-hint">
          Điền sẵn các ô giọng đọc khi bạn tạo một Template mới từ "Blank" (Video Factory Templates bên dưới). Không
          đổi Template hay project nào đang có -- mỗi Template giữ cấu hình riêng của nó.
        </p>

        <div className="settings-row">
          <label className="settings-label" htmlFor="default-voice-provider">
            Provider
          </label>
          <select
            id="default-voice-provider"
            className="settings-input settings-input-narrow"
            value={defaultVoiceProvider}
            onChange={(e) => {
              setDefaultVoiceProvider(e.target.value as "local" | "edge_tts");
              setDefaultVoiceId("default");
            }}
          >
            <option value="local">Local (offline, không cần mạng)</option>
            <option value="edge_tts">Edge TTS (miễn phí, cần mạng)</option>
          </select>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="default-voice-id">
            Giọng
          </label>
          <select
            id="default-voice-id"
            className="settings-input settings-input-narrow"
            value={defaultVoiceId}
            onChange={(e) => setDefaultVoiceId(e.target.value)}
          >
            {defaultVoiceProvider === "local" ? (
              <>
                <option value="default">System Default</option>
                {localVoices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </>
            ) : (
              <>
                <option value="default">Mặc định theo ngôn ngữ</option>
                {VOICE_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </>
            )}
          </select>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="default-voice-speed">
            Tốc độ ({defaultVoiceSpeed.toFixed(2)}x)
          </label>
          <input
            id="default-voice-speed"
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={defaultVoiceSpeed}
            onChange={(e) => setDefaultVoiceSpeed(Number(e.target.value))}
          />
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="default-sentence-pause">
            Khoảng lặng giữa câu ({defaultSentencePause.toFixed(2)}s)
          </label>
          <input
            id="default-sentence-pause"
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={defaultSentencePause}
            onChange={(e) => setDefaultSentencePause(Number(e.target.value))}
          />
        </div>
        <p className="settings-hint">
          Khoảng im lặng chèn giữa các câu/beat. 0.35s là mặc định cho giọng kể ấm; tăng lên ~0.8-1.5s cho kiểu
          "nhấn nhá" chậm rãi (horror, podcast deadpan).
        </p>

        <div className="settings-row">
          <span className="settings-label" />
          <button className="btn btn-secondary" onClick={handleSaveDefaultVoice} disabled={savingDefaultVoice}>
            <CheckCircle2 size={14} />
            Lưu giọng mặc định
          </button>
        </div>
      </div>

      {/* -- TikTok ------------------------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">TikTok (Competitor Content Analyzer)</label>
        </div>
        <p className="settings-hint">
          Cần một TikTok Developer app do bạn tự đăng ký tại developers.tiktok.com (Client Key/Secret) và một Redirect
          URI dạng HTTPS mà bạn đã đăng ký với app đó -- TikTok yêu cầu HTTPS, ứng dụng desktop này không thể tự tạo
          hay phê duyệt bước này. App mới của bạn cũng cần được TikTok duyệt scope trước khi dùng được với tài khoản
          thật (ngoài danh sách sandbox test user).
        </p>

        <div className="settings-row">
          <label className="settings-label" htmlFor="tiktok-client-key">
            TikTok Client Key
          </label>
          <div className="settings-folder-picker">
            <input
              id="tiktok-client-key"
              type="password"
              className="settings-input"
              placeholder={hasTikTokClientKey ? "•••••••••••••• (đã cấu hình)" : "aw..."}
              value={tiktokClientKeyInput}
              onChange={(e) => setTiktokClientKeyInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveTikTokClientKey}
              disabled={!tiktokClientKeyInput.trim() || savingTikTokClientKey}
            >
              {hasTikTokClientKey && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="tiktok-client-secret">
            TikTok Client Secret
          </label>
          <div className="settings-folder-picker">
            <input
              id="tiktok-client-secret"
              type="password"
              className="settings-input"
              placeholder={hasTikTokClientSecret ? "•••••••••••••• (đã cấu hình)" : "..."}
              value={tiktokClientSecretInput}
              onChange={(e) => setTiktokClientSecretInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveTikTokClientSecret}
              disabled={!tiktokClientSecretInput.trim() || savingTikTokClientSecret}
            >
              {hasTikTokClientSecret && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="tiktok-redirect-uri">
            TikTok Redirect URI
          </label>
          <div className="settings-folder-picker">
            <input
              id="tiktok-redirect-uri"
              type="text"
              className="settings-input"
              placeholder={tiktokRedirectUri ?? "https://your-domain.example/tiktok/callback"}
              value={tiktokRedirectUriInput}
              onChange={(e) => setTiktokRedirectUriInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveTikTokRedirectUri}
              disabled={!tiktokRedirectUriInput.trim() || savingTikTokRedirectUri}
            >
              {tiktokRedirectUri && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>
      </div>

      {/* -- YouTube Publishing ----------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">YouTube Publishing (Google OAuth)</label>
        </div>
        <p className="settings-hint">
          Tạo project trên Google Cloud Console → bật <strong>YouTube Data API v3</strong> → tạo OAuth client loại
          "Desktop app" → thêm Redirect URI dưới đây vào client đó → dán Client ID / Secret vào ô này.
          {hasGoogleOAuth ? " Đã cấu hình." : ""}
        </p>
        <div className="settings-row">
          <label className="settings-label" htmlFor="google-client-id">Client ID</label>
          <input
            id="google-client-id"
            type="text"
            className="settings-input"
            placeholder={hasGoogleOAuth ? "••• (đã lưu)" : "xxxxx.apps.googleusercontent.com"}
            value={googleClientIdInput}
            onChange={(e) => setGoogleClientIdInput(e.target.value)}
          />
        </div>
        <div className="settings-row">
          <label className="settings-label" htmlFor="google-client-secret">Client Secret</label>
          <div className="settings-folder-picker">
            <input
              id="google-client-secret"
              type="password"
              className="settings-input"
              placeholder={hasGoogleOAuth ? "••• (đã lưu)" : "GOCSPX-..."}
              value={googleClientSecretInput}
              onChange={(e) => setGoogleClientSecretInput(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              onClick={handleSaveGoogleOAuth}
              disabled={!googleClientIdInput.trim() || !googleClientSecretInput.trim() || savingGoogleOAuth}
            >
              {hasGoogleOAuth && <CheckCircle2 size={14} />}
              Lưu
            </button>
          </div>
        </div>
        <div className="settings-row">
          <label className="settings-label">Redirect URI (dán vào Google Console)</label>
          <input className="settings-input" type="text" readOnly value={youtubeRedirectUri} onFocus={(e) => e.target.select()} />
        </div>
      </div>

      {/* -- Tự động kéo tin RSS --------------------------------------- */}
      <div className="settings-card">
        <div className="settings-row settings-row-header">
          <label className="settings-label">Tự động kéo tin tức (RSS)</label>
        </div>
        <p className="settings-hint">
          Trang Tin tức sẽ tự động kéo bài mới từ tất cả nguồn RSS đang bật, theo chu kỳ dưới đây (lúc mở app
          và mỗi khoảng thời gian này). 0 = tắt, chỉ kéo khi bạn bấm "Kéo tất cả".
        </p>
        <div className="settings-row">
          <label className="settings-label" htmlFor="news-poll-minutes">
            Kéo mỗi
          </label>
          <select
            id="news-poll-minutes"
            className="settings-input settings-input-narrow"
            value={newsPollMinutes}
            disabled={savingNewsPoll}
            onChange={(e) => handleSaveNewsPoll(Number(e.target.value))}
          >
            <option value={0}>Tắt</option>
            <option value={15}>15 phút</option>
            <option value={30}>30 phút</option>
            <option value={60}>60 phút</option>
            <option value={180}>3 giờ</option>
          </select>
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
          defaultVoice={{
            provider: defaultVoiceProvider,
            voice_id: defaultVoiceId,
            speed: defaultVoiceSpeed,
            sentence_pause_sec: defaultSentencePause,
          }}
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
