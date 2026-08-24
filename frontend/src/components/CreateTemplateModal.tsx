import { Fragment, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Music, Save, Trash2, X } from "lucide-react";
import { assetFileUrl, getAsset } from "../api/asset";
import { createTemplate } from "../api/template";
import { AssetBrowserModal } from "./AssetBrowserModal";
import { SYSTEM_DEFAULT_PROJECT_CONFIG } from "../types/videoFactory";
import type { ProjectConfig, Template } from "../types/videoFactory";
import "./EditTemplateModal.css";

interface CreateTemplateModalProps {
  // Real user report: Settings' "Video Factory Templates" card was
  // list+edit+delete only for custom templates -- no way to create a new
  // one at all (built-ins can't be edited, and the only other "create"
  // path -- VideoFactoryPage's "Save as Template" -- requires an
  // already-in-progress project). Reuses the backend's existing
  // POST /templates (router.py's create_template) -- see
  // docs/features/84-template-management-and-image-style-prompt.md for the
  // sibling edit flow this mirrors.
  existingTemplates: Template[];
  onSaved: (template: Template) => void;
  onClose: () => void;
}

// Same narrow edit surface as EditTemplateModal (name/description/image
// style prompt/music) -- no full ProjectConfig editor exists anywhere in
// this app to reuse (VideoFactoryPage's own wizard is project-authoring
// UI, not an isolated form component), so a new template starts from
// either plain system defaults or a copy of an existing template's full
// config, with only this same narrow subset exposed for editing here --
// consistent with what EditTemplateModal already lets a user change after
// creation, and matching Template.config's own "everything else stays as
// the source had it" semantics (mirrors Batch.template_id's own snapshot
// convention, not a live link to the source template).
export function CreateTemplateModal({ existingTemplates, onSaved, onClose }: CreateTemplateModalProps) {
  const [sourceTemplateId, setSourceTemplateId] = useState<string>("__blank__");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [imageStylePrompt, setImageStylePrompt] = useState("");
  const [musicEnabled, setMusicEnabled] = useState(SYSTEM_DEFAULT_PROJECT_CONFIG.audio.music_enabled);
  const [musicAssetId, setMusicAssetId] = useState<number | null>(null);
  const [musicAssetName, setMusicAssetName] = useState<string | null>(null);
  const [musicBrowserOpen, setMusicBrowserOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function sourceConfig(): ProjectConfig {
    const source = existingTemplates.find((t) => t.id === sourceTemplateId);
    return source ? source.config : SYSTEM_DEFAULT_PROJECT_CONFIG;
  }

  function handleSourceChange(id: string) {
    setSourceTemplateId(id);
    const config = id === "__blank__" ? SYSTEM_DEFAULT_PROJECT_CONFIG : existingTemplates.find((t) => t.id === id)?.config;
    if (!config) return;
    setImageStylePrompt(config.visual_generation.image_style_prompt);
    setMusicEnabled(config.audio.music_enabled);
    setMusicAssetId(config.audio.bgm_asset_id);
  }

  useEffect(() => {
    if (musicAssetId == null) {
      setMusicAssetName(null);
      return;
    }
    getAsset(musicAssetId)
      .then((asset) => setMusicAssetName(asset.filename))
      .catch(() => setMusicAssetName(null));
  }, [musicAssetId]);

  async function handleCreate() {
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const base = sourceConfig();
      // sanitize_project_config_for_template on the backend strips template
      // provenance (template_id/template_version) automatically -- no need
      // to clear them here (same precedent VideoFactoryPage.tsx's own
      // "Save as Template" flow already established).
      const created = await createTemplate({
        name: name.trim(),
        description,
        config: {
          ...base,
          visual_generation: { ...base.visual_generation, image_style_prompt: imageStylePrompt },
          audio: {
            ...base.audio,
            music_enabled: musicEnabled,
            bgm_mode: musicAssetId != null ? "MANUAL" : "AUTO",
            bgm_asset_id: musicAssetId,
          },
        },
      });
      onSaved(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create template.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Fragment>
      <div className="edit-template-modal-overlay" onClick={onClose}>
        <div className="edit-template-modal" onClick={(e) => e.stopPropagation()}>
          <div className="edit-template-modal-header">
            <span>New Template</span>
            <button className="edit-template-modal-close" onClick={onClose}>
              <X size={16} />
            </button>
          </div>

          <div className="edit-template-modal-body">
            <label className="edit-template-field">
              <span>Start from</span>
              <select value={sourceTemplateId} onChange={(e) => handleSourceChange(e.target.value)}>
                <option value="__blank__">Blank (plain system defaults)</option>
                {existingTemplates.map((t) => (
                  <option key={t.id} value={t.id}>
                    Copy of "{t.name}"
                  </option>
                ))}
              </select>
              <span className="edit-template-hint">
                Copies that template's full settings (render, motion, captions, voice, etc.) as a one-time starting
                point -- not a live link, editing this new template later never affects the source.
              </span>
            </label>

            <label className="edit-template-field">
              <span>Name</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </label>

            <label className="edit-template-field">
              <span>Description</span>
              <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>

            <label className="edit-template-field">
              <span>Image style prompt</span>
              <textarea
                rows={3}
                placeholder="e.g. watercolor illustration, soft pastel colors, hand-drawn feel"
                value={imageStylePrompt}
                onChange={(e) => setImageStylePrompt(e.target.value)}
              />
              <span className="edit-template-hint">
                Appended to every AI-generated beat image for projects using this template. Free -- image
                generation is a flat per-image fee regardless of prompt length.
              </span>
            </label>

            <label className="edit-template-checkbox">
              <input type="checkbox" checked={musicEnabled} onChange={(e) => setMusicEnabled(e.target.checked)} />
              <span>Background music</span>
            </label>

            {musicEnabled && (
              <div className="edit-template-field">
                <span>Track</span>
                <div className="edit-template-music-row">
                  <span className="edit-template-music-name">
                    {musicAssetId != null ? musicAssetName ?? `Asset #${musicAssetId}` : "Automatic (picked by tone)"}
                  </span>
                  <button className="btn btn-secondary" onClick={() => setMusicBrowserOpen(true)}>
                    <Music size={13} />
                    Choose Music
                  </button>
                  {musicAssetId != null && (
                    <button className="btn btn-secondary" onClick={() => setMusicAssetId(null)}>
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
                {musicAssetId != null && (
                  <audio className="edit-template-audio-preview" src={assetFileUrl(musicAssetId)} controls preload="none" />
                )}
                <span className="edit-template-hint">
                  {musicAssetId != null
                    ? "Projects using this template will use this exact track."
                    : "No track chosen -- projects will get a track picked automatically by content tone, which can pick unexpectedly if the library isn't curated."}
                </span>
              </div>
            )}

            {error && (
              <div className="edit-template-error">
                <AlertTriangle size={14} />
                {error}
              </div>
            )}
          </div>

          <div className="edit-template-modal-actions">
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim() || saving}>
              {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
              Create
            </button>
          </div>
        </div>
      </div>

      {musicBrowserOpen && (
        <AssetBrowserModal
          assetType="audio"
          onSelect={(asset) => {
            setMusicAssetId(asset.id);
            setMusicBrowserOpen(false);
          }}
          onClose={() => setMusicBrowserOpen(false)}
        />
      )}
    </Fragment>
  );
}
