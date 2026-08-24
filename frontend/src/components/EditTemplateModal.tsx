import { Fragment, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Music, Save, Trash2, X } from "lucide-react";
import { assetFileUrl, getAsset } from "../api/asset";
import { updateTemplate } from "../api/template";
import { listLocalVoices } from "../api/voice";
import type { LocalVoiceOption } from "../api/voice";
import { AssetBrowserModal } from "./AssetBrowserModal";
import { CAPTION_PRESETS, CAPTION_PRESET_LABELS, VOICE_OPTIONS } from "../types/videoFactory";
import type { CaptionPreset, Template } from "../types/videoFactory";
import "./EditTemplateModal.css";

interface EditTemplateModalProps {
  template: Template;
  onSaved: (template: Template) => void;
  onClose: () => void;
}

// Edit surface for an existing custom Template (Settings' "Video Factory
// Templates" card was list+create-via-snapshot+delete only -- real user
// report: no way to rename/re-describe a saved template, set an image
// style prompt, or pick background music without recreating it from
// scratch). Reuses the backend's existing upsert-by-id PUT /templates/{id}
// (router.py's update_template) -- see
// docs/features/84-template-management-and-image-style-prompt.md.
//
// The music picker mirrors VideoFactoryPage's own "Choose Music" widget
// exactly (same AssetBrowserModal assetType="audio", same "nothing chosen
// -> AUTO, a specific track -> MANUAL bgm_mode" semantics -- see real user
// report in docs/features/86-narration-disabled-audio-master-failfast.md's
// follow-up where AUTO mode picked a stray narration test file as "music"
// for lack of any better signal) -- picking an exact track here is what
// makes AUTO's ambiguity a non-issue for this template going forward.
//
// Rendered as a Fragment (not nested inside the edit modal's own backdrop
// div) so a click dismissing the AssetBrowserModal's own backdrop doesn't
// bubble up and also close this modal -- AssetBrowserModal's backdrop
// onClick has no stopPropagation of its own, same as this modal's.
export function EditTemplateModal({ template, onSaved, onClose }: EditTemplateModalProps) {
  const [name, setName] = useState(template.name);
  const [description, setDescription] = useState(template.description);
  const [imageStylePrompt, setImageStylePrompt] = useState(template.config.visual_generation.image_style_prompt);
  const [musicEnabled, setMusicEnabled] = useState(template.config.audio.music_enabled);
  const [musicAssetId, setMusicAssetId] = useState<number | null>(template.config.audio.bgm_asset_id);
  const [musicAssetName, setMusicAssetName] = useState<string | null>(null);
  const [musicBrowserOpen, setMusicBrowserOpen] = useState(false);
  // Real user report: this modal had no captions/voice controls at all --
  // a template's own caption preset/voice were silently carried over
  // unseen and unchangeable (the built-in "Emotional Story" template, for
  // example, actually uses the "big_statement" preset -- large, centered
  // text -- despite its name; there was no way to notice or fix that here).
  const [captionsEnabled, setCaptionsEnabled] = useState(template.config.captions.enabled);
  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>(template.config.captions.preset);
  const [voiceProvider, setVoiceProvider] = useState(template.config.voice.provider);
  const [voiceId, setVoiceId] = useState(template.config.voice.voice_id);
  const [voiceSpeed, setVoiceSpeed] = useState(template.config.voice.speed);
  const [localVoices, setLocalVoices] = useState<LocalVoiceOption[]>([]);
  const [localVoicesError, setLocalVoicesError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (musicAssetId == null) {
      setMusicAssetName(null);
      return;
    }
    getAsset(musicAssetId)
      .then((asset) => setMusicAssetName(asset.filename))
      .catch(() => setMusicAssetName(null));
  }, [musicAssetId]);

  useEffect(() => {
    listLocalVoices()
      .then(setLocalVoices)
      .catch((err) => setLocalVoicesError(err instanceof Error ? err.message : "Could not load local voices."));
  }, []);

  async function handleSave() {
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateTemplate(template.id, {
        name: name.trim(),
        description,
        config: {
          ...template.config,
          visual_generation: { ...template.config.visual_generation, image_style_prompt: imageStylePrompt },
          audio: {
            ...template.config.audio,
            music_enabled: musicEnabled,
            bgm_mode: musicAssetId != null ? "MANUAL" : "AUTO",
            bgm_asset_id: musicAssetId,
          },
          captions: { ...template.config.captions, enabled: captionsEnabled, preset: captionPreset },
          voice: { ...template.config.voice, provider: voiceProvider, voice_id: voiceId, speed: voiceSpeed },
        },
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save template.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Fragment>
      <div className="edit-template-modal-overlay" onClick={onClose}>
        <div className="edit-template-modal" onClick={(e) => e.stopPropagation()}>
          <div className="edit-template-modal-header">
            <span>Edit Template</span>
            <button className="edit-template-modal-close" onClick={onClose}>
              <X size={16} />
            </button>
          </div>

          <div className="edit-template-modal-body">
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
              <input type="checkbox" checked={captionsEnabled} onChange={(e) => setCaptionsEnabled(e.target.checked)} />
              <span>Captions</span>
            </label>

            {captionsEnabled && (
              <label className="edit-template-field">
                <span>Caption style (controls text size and position)</span>
                <select value={captionPreset} onChange={(e) => setCaptionPreset(e.target.value as CaptionPreset)}>
                  {CAPTION_PRESETS.map((preset) => (
                    <option key={preset} value={preset}>
                      {CAPTION_PRESET_LABELS[preset]}
                    </option>
                  ))}
                </select>
                <span className="edit-template-hint">
                  "Big statement" is large and vertically centered; "Emotional"/"Cinematic"/"Word highlight"/"Top"
                  sit near the bottom or top edge instead.
                </span>
              </label>
            )}

            <label className="edit-template-field">
              <span>Voice provider</span>
              <select
                value={voiceProvider}
                onChange={(e) => {
                  const next = e.target.value as typeof voiceProvider;
                  setVoiceProvider(next);
                  setVoiceId("default");
                }}
              >
                <option value="local">Local (offline, no network)</option>
                <option value="edge_tts">Edge TTS (free, requires network)</option>
              </select>
            </label>

            {voiceProvider === "local" ? (
              <label className="edit-template-field">
                <span>Voice</span>
                <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                  <option value="default">System Default</option>
                  {localVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
                {localVoicesError && (
                  <span className="edit-template-hint">{localVoicesError}</span>
                )}
              </label>
            ) : (
              <label className="edit-template-field">
                <span>Voice</span>
                <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                  <option value="default">Default for language</option>
                  {VOICE_OPTIONS.map((v) => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="edit-template-field">
              <span>Voice speed ({voiceSpeed.toFixed(2)}x)</span>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={voiceSpeed}
                onChange={(e) => setVoiceSpeed(Number(e.target.value))}
              />
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
            <button className="btn btn-primary" onClick={handleSave} disabled={!name.trim() || saving}>
              {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
              Save
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
