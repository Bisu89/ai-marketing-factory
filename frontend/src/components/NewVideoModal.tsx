import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, X } from "lucide-react";
import { createProject } from "../api/beat";
import { listTemplates } from "../api/template";
import { startFactoryRun } from "../api/factory";
import type { Template } from "../types/videoFactory";
import "./NewVideoModal.css";

interface NewVideoModalProps {
  onClose: () => void;
}

// Task 18's one-click "New Video" entry point (section 29 -- see
// docs/features/44-one-click-factory-pipeline.md): Template + Name +
// Script + "Produce automatically". Creates a real, id-addressable
// Project (POST /projects, reusing app.modules.beat.project_service's
// existing create_project -- not a second creation flow) and, if checked,
// immediately starts a FactoryRun for it. Does not touch or replace the
// classic template-picker "New Video" entry already on VideoFactoryPage
// (opened via /video-factory with no ?project= -- still the singleton
// beats.json flow, untouched).
export function NewVideoModal({ onClose }: NewVideoModalProps) {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [script, setScript] = useState("");
  const [autoProduce, setAutoProduce] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await listTemplates();
        setTemplates(list);
        if (list.length > 0) setTemplateId(list[0].id);
      } catch (err) {
        setTemplatesError(err instanceof Error ? err.message : "Could not load templates.");
      }
    })();
  }, []);

  async function handleSubmit() {
    if (!name.trim() || !templateId || !script.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const project = await createProject({ name, script_text: script, template_id: templateId });
      if (autoProduce) {
        await startFactoryRun(project.id);
      }
      navigate(`/video-factory?project=${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this project.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="nvm-backdrop" onClick={onClose}>
      <div className="nvm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="nvm-header">
          <h3>New Video</h3>
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
          <span>Project name</span>
          <input type="text" placeholder="My Video" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <label className="nvm-field">
          <span>Script</span>
          <textarea rows={8} placeholder="Paste or write the narration script..." value={script} onChange={(e) => setScript(e.target.value)} />
        </label>

        <label className="nvm-checkbox">
          <input type="checkbox" checked={autoProduce} onChange={(e) => setAutoProduce(e.target.checked)} />
          <span>Produce automatically</span>
        </label>
        <p className="nvm-hint">
          {autoProduce
            ? "Beats, visuals, and quality check run automatically; render starts as soon as it's ready."
            : "Only the project is created -- generate beats and assign visuals yourself when ready."}
        </p>

        <div className="nvm-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={busy || !name.trim() || !templateId || !script.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            {autoProduce ? "Create & Produce" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
