import { useState } from "react";
import { AlertTriangle, Loader2, Save, X } from "lucide-react";
import { updateTemplate } from "../api/template";
import type { Template } from "../types/videoFactory";
import "./EditTemplateModal.css";

interface EditTemplateModalProps {
  template: Template;
  onSaved: (template: Template) => void;
  onClose: () => void;
}

// Edit surface for an existing custom Template (Settings' "Video Factory
// Templates" card was list+create-via-snapshot+delete only -- real user
// report: no way to rename/re-describe a saved template, or to set an
// image style prompt without recreating it from scratch). Reuses the
// backend's existing upsert-by-id PUT /templates/{id} (router.py's
// update_template) -- see docs/features/84-template-management-and-image-style-prompt.md.
export function EditTemplateModal({ template, onSaved, onClose }: EditTemplateModalProps) {
  const [name, setName] = useState(template.name);
  const [description, setDescription] = useState(template.description);
  const [imageStylePrompt, setImageStylePrompt] = useState(template.config.visual_generation.image_style_prompt);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
  );
}
