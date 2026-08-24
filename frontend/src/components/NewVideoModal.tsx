import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Sparkles, X } from "lucide-react";
import { createProject } from "../api/beat";
import { listTemplates } from "../api/template";
import { startFactoryRun } from "../api/factory";
import { getSettings } from "../api/settings";
import { attachProjectToSeries } from "../api/series";
import { CONTENT_LANGUAGES, CONTENT_LANGUAGE_LABELS } from "../types/videoFactory";
import type { ContentLanguage, Template } from "../types/videoFactory";
import "./NewVideoModal.css";

// Task 59 -- see docs/features/59-ai-image-generation.md. Mirrors
// app.modules.ai.image_client.IMAGE_COST_USD (backend is the source of
// truth for the real per-image price; this is only a rough, static
// pre-creation estimate shown before the real beat count is known --
// the real, per-run count/cost is shown afterward on ReadyToPostCard).
const IMAGE_COST_USD_ESTIMATE = 0.006;
const TYPICAL_BEAT_COUNT_RANGE = [6, 8] as const;

// Real user report: Template and Content language reset to the hardcoded
// default every time this modal reopens, forcing a re-pick on every single
// video even though most users pick the same one repeatedly. Remembered
// client-side (this modal has no per-user account/profile concept to
// persist to server-side) -- read once on open, written back whenever
// either changes.
const LAST_TEMPLATE_ID_KEY = "nvm:lastTemplateId";
const LAST_CONTENT_LANGUAGE_KEY = "nvm:lastContentLanguage";

interface NewVideoModalProps {
  onClose: () => void;
  // Series (scoped-down "100-Day Series") -- when opened from
  // SeriesDetailPage.tsx's "+ New Episode" button, the created project is
  // attached to this series as a second step right after creation (mirrors
  // this component's own existing create-then-maybe-startFactoryRun
  // two-step shape). Not exposed as a picker in the normal "New Video"
  // entry point -- Series creation/attachment is a deliberately separate,
  // opt-in flow, not a field every video creation shows.
  seriesId?: number;
}

// Task 18's one-click "New Video" entry point (section 29 -- see
// docs/features/44-one-click-factory-pipeline.md): Template + Name +
// Idea-or-Script + "Produce automatically". Creates a real, id-addressable
// Project (POST /projects, reusing app.modules.beat.project_service's
// existing create_project -- not a second creation flow) and, if checked,
// immediately starts a FactoryRun for it. Does not touch or replace the
// classic template-picker "New Video" entry already on VideoFactoryPage
// (opened via /video-factory with no ?project= -- still the singleton
// beats.json flow, untouched).
//
// Task 21 (see docs/features/47-content-brief-script-engine.md) adds Idea
// as an alternative to Script -- exactly one is sent; entering either one
// disables the other rather than allowing both, since the backend only
// accepts one anyway (a script always skips AI content generation, section
// 43's own explicit example).
export function NewVideoModal({ onClose, seriesId }: NewVideoModalProps) {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState("");
  // Real user report: this modal had no language control at all, so every
  // Template's own hardcoded "en" was the only possible outcome -- see
  // docs/features/79-new-video-modal-language.md. Falls back to "en"
  // (every built-in Template's own default) only when nothing was
  // remembered yet from a previous open.
  const [contentLanguage, setContentLanguage] = useState<ContentLanguage>(() => {
    const remembered = localStorage.getItem(LAST_CONTENT_LANGUAGE_KEY);
    return remembered && (CONTENT_LANGUAGES as readonly string[]).includes(remembered)
      ? (remembered as ContentLanguage)
      : "en";
  });
  const [name, setName] = useState("");
  // Task 21 (see docs/features/47-content-brief-script-engine.md) -- an
  // Idea and a Script are alternative inputs, not both required. Entering a
  // Script directly always skips AI content generation entirely (section 43's
  // own explicit example), so idea is cleared the moment the user types a
  // script and vice versa -- exactly one of the two is ever sent.
  const [idea, setIdea] = useState("");
  const [script, setScript] = useState("");
  // Outro Card (docs/features/89-outro-card.md) -- real user follow-up:
  // "what about Generate Full by AI?" That flow creates the Project and
  // starts the FactoryRun in one call, before there's ever a BeatPlan to
  // attach a Step-4-style edit to, so this has to be settable here, at
  // creation time, or not at all. Blank means no outro (unchanged
  // behavior for the auto-produce/classic paths below).
  const [outroText, setOutroText] = useState("");
  // Package AI Metadata -- real user report that the deterministic
  // title/description/thumbnail text felt bland (bland core_message
  // truncation, thumbnail always echoing the exact same text as the
  // title). Off by default -- a real, billed AI call, unlike everything
  // else this modal sets. Not persisted across opens (unlike Template/
  // Content language) -- same reasoning as autoProduce not being
  // persisted either.
  const [aiMetadataEnabled, setAiMetadataEnabled] = useState(false);
  const [autoProduce, setAutoProduce] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasOpenAiKey, setHasOpenAiKey] = useState(true); // optimistic default -- avoids a flash of "disabled" before settings load

  useEffect(() => {
    (async () => {
      try {
        const list = await listTemplates();
        setTemplates(list);
        if (list.length > 0) {
          const remembered = localStorage.getItem(LAST_TEMPLATE_ID_KEY);
          const stillExists = remembered && list.some((t) => t.id === remembered);
          setTemplateId(stillExists ? remembered! : list[0].id);
        }
      } catch (err) {
        setTemplatesError(err instanceof Error ? err.message : "Could not load templates.");
      }
    })();
    getSettings()
      .then((s) => setHasOpenAiKey(s.has_openai_key))
      .catch(() => setHasOpenAiKey(false));
  }, []);

  useEffect(() => {
    if (templateId) localStorage.setItem(LAST_TEMPLATE_ID_KEY, templateId);
  }, [templateId]);

  useEffect(() => {
    localStorage.setItem(LAST_CONTENT_LANGUAGE_KEY, contentLanguage);
  }, [contentLanguage]);

  const hasContent = script.trim().length > 0 || idea.trim().length > 0;
  const hasStory = script.trim().length > 0;
  const [lowBeats, highBeats] = TYPICAL_BEAT_COUNT_RANGE;
  const lowEstimate = (lowBeats * IMAGE_COST_USD_ESTIMATE).toFixed(2);
  const highEstimate = (highBeats * IMAGE_COST_USD_ESTIMATE).toFixed(2);

  async function handleSubmit() {
    if (!name.trim() || !templateId || !hasContent || busy) return;
    setBusy(true);
    setError(null);
    try {
      const project = await createProject({
        name,
        script_text: script.trim() ? script : null,
        idea: script.trim() ? null : idea.trim() ? idea : null,
        template_id: templateId,
        content_language: contentLanguage,
        outro_text: outroText.trim() || null,
        ai_metadata_enabled: aiMetadataEnabled,
      });
      if (seriesId != null) {
        await attachProjectToSeries(project.id, seriesId);
      }
      if (autoProduce) {
        await startFactoryRun(project.id);
      }
      onClose();
      navigate(`/video-factory?project=${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this project.");
    } finally {
      setBusy(false);
    }
  }

  // Task 59 (see docs/features/59-ai-image-generation.md): a distinct
  // entry point, not a checkbox on the existing flow -- "paste a full
  // story, get a produced video back, with a fresh AI image per beat
  // instead of matched from the Asset Library." Always produces
  // automatically (no separate autoProduce choice for this button, per the
  // user's own "I just input the story, you do the rest" request).
  async function handleGenerateFullByAI() {
    if (!name.trim() || !templateId || !hasStory || busy) return;
    setBusy(true);
    setError(null);
    try {
      const project = await createProject({
        name, script_text: script, idea: null, template_id: templateId, visual_generation_mode: "ai_generated",
        content_language: contentLanguage, outro_text: outroText.trim() || null,
        ai_metadata_enabled: aiMetadataEnabled,
      });
      if (seriesId != null) {
        // Must happen before startFactoryRun -- the Factory pipeline's own
        // GENERATING_VISUALS stage reads this project's image_style_prompt
        // as soon as it runs, so the series' character description needs
        // to already be folded in by then.
        await attachProjectToSeries(project.id, seriesId);
      }
      await startFactoryRun(project.id);
      onClose();
      navigate(`/video-factory?project=${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this project.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="nvm-backdrop">
      <div className="nvm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="nvm-header">
          <h3>{seriesId != null ? "New Episode" : "New Video"}</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="nvm-alert">{error}</div>}

        <label className="nvm-field">
          <span>Template</span>
          {templatesError ? (
            <span className="nvm-field-error">{templatesError}</span>
          ) : (
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.builtin ? " (built-in)" : ""}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="nvm-field">
          <span>Content language (script text + narration)</span>
          <select value={contentLanguage} onChange={(e) => setContentLanguage(e.target.value as ContentLanguage)}>
            {CONTENT_LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {CONTENT_LANGUAGE_LABELS[lang]}
              </option>
            ))}
          </select>
        </label>
        {contentLanguage !== "en" && (
          <p className="nvm-hint">
            Voice Factory automatically uses Edge TTS for non-English narration -- Local (offline) voices may not
            have a {CONTENT_LANGUAGE_LABELS[contentLanguage]} voice installed on this machine.
          </p>
        )}

        <label className="nvm-field">
          <span>Project name</span>
          <input type="text" placeholder="My Video" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <label className="nvm-field">
          <span>Idea</span>
          <input
            type="text"
            placeholder="Why couples stop talking after five years"
            value={idea}
            disabled={script.trim().length > 0}
            onChange={(e) => setIdea(e.target.value)}
          />
        </label>
        <p className="nvm-hint">
          Produce will turn this into a Content Brief and a Script automatically. Leave blank and write a Script
          below instead to skip AI content generation entirely.
        </p>

        <label className="nvm-field">
          <span>Script (optional if an Idea is set)</span>
          <textarea
            rows={6}
            placeholder="Paste or write the narration script..."
            value={script}
            disabled={idea.trim().length > 0}
            onChange={(e) => setScript(e.target.value)}
          />
        </label>

        <label className="nvm-field">
          <span>Ending text (outro, optional)</span>
          <textarea
            rows={3}
            maxLength={200}
            placeholder="e.g. Theo doi de xem phan 2 nhe!"
            value={outroText}
            onChange={(e) => setOutroText(e.target.value)}
          />
        </label>
        <p className="nvm-hint">
          {outroText.trim()
            ? "Appended after the video: black background, this text typed on screen, background music swelling to full volume. Never taken from the script."
            : "Optional -- leave blank for no outro. Fine-tune duration later on the project's own Audio step."}
        </p>

        <label className="nvm-checkbox">
          <input type="checkbox" checked={autoProduce} onChange={(e) => setAutoProduce(e.target.checked)} />
          <span>Produce automatically</span>
        </label>
        <p className="nvm-hint">
          {autoProduce
            ? "Content (if starting from an Idea), beats, visuals, and quality check run automatically; render starts as soon as it's ready."
            : "Only the project is created -- generate content/beats and assign visuals yourself when ready."}
        </p>

        <div className="nvm-ai-generate">
          <label className="nvm-checkbox">
            <input type="checkbox" checked={aiMetadataEnabled} onChange={(e) => setAiMetadataEnabled(e.target.checked)} />
            <span>AI-write title, description &amp; thumbnail text</span>
          </label>
          <p className="nvm-hint">
            Rewrites the title/description/thumbnail text for a punchier hook instead of the default (a plain
            truncated summary). A small extra AI cost -- roughly $0.01 or less per video.
          </p>

          <button
            className="btn btn-primary nvm-ai-generate-btn"
            onClick={handleGenerateFullByAI}
            disabled={busy || !name.trim() || !templateId || !hasStory || !hasOpenAiKey}
          >
            {busy ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            Generate Full by AI
          </button>
          <p className="nvm-hint">
            {hasOpenAiKey
              ? `Paste the whole story into Script above -- beats, a fresh AI image per beat (OpenAI), narration, and render all run automatically. Estimated image cost: ~$${lowEstimate}-$${highEstimate} for a typical ${lowBeats}-${highBeats} beat video.`
              : "Requires an OpenAI API key -- add one in Settings to use AI image generation."}
          </p>
        </div>

        <div className="nvm-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={busy || !name.trim() || !templateId || !hasContent}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            {autoProduce ? "Create & Produce" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
