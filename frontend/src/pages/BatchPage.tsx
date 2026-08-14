import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Layers, Loader2, Plus, Upload, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { createBatch, listBatches, previewBatch } from "../api/batch";
import { listTemplates } from "../api/template";
import type { Batch, BatchPreview } from "../types/batch";
import type { Template } from "../types/videoFactory";
import "./BatchPage.css";

const STATUS_LABEL: Record<Batch["status"], string> = {
  DRAFT: "Draft",
  PROCESSING: "Processing",
  COMPLETED: "Completed",
  PARTIAL_FAILURE: "Partial failure",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

function itemSummary(batch: Batch): string {
  const total = batch.items.length;
  const completed = batch.items.filter((i) => i.status === "COMPLETED").length;
  return `${completed}/${total} completed`;
}

export function BatchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Deep-link support for the Production Dashboard's "New Batch" CTA
  // (see docs/features/43-production-dashboard.md) -- opens the exact
  // same modal below, no separate creation flow.
  const [createOpen, setCreateOpen] = useState(searchParams.get("new") === "1");

  useEffect(() => {
    if (searchParams.get("new") === "1") {
      setSearchParams((params) => {
        params.delete("new");
        return params;
      }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refresh() {
    try {
      setLoadError(null);
      setBatches(await listBatches());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load batches.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <PageHeader
        title="Batches"
        subtitle="Turn many scripts into many projects at once -- one template applied to all, rendered through the same local queue."
        actions={
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus size={14} />
            New Batch
          </button>
        }
      />

      {loadError && <div className="batch-alert batch-alert-error">{loadError}</div>}

      {batches.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No batches yet"
          description="Create a batch to turn a stack of scripts into that many projects, all sharing one template."
        />
      ) : (
        <div className="batch-table-wrap">
          <table className="batch-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Template</th>
                <th>Status</th>
                <th>Items</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => (
                <tr key={batch.id} onClick={() => navigate(`/batches/${batch.id}`)} className="batch-row-clickable">
                  <td>{batch.name}</td>
                  <td>{batch.template_id ?? "--"}</td>
                  <td>
                    <span className={`batch-status batch-status--${batch.status}`}>{STATUS_LABEL[batch.status]}</span>
                  </td>
                  <td>{itemSummary(batch)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateBatchModal
          onClose={() => setCreateOpen(false)}
          onCreated={(batch) => {
            setCreateOpen(false);
            navigate(`/batches/${batch.id}`);
          }}
        />
      )}
    </>
  );
}

type CreateStep = "form" | "preview";

function CreateBatchModal({ onClose, onCreated }: { onClose: () => void; onCreated: (batch: Batch) => void }) {
  const [step, setStep] = useState<CreateStep>("form");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [scriptsText, setScriptsText] = useState("");
  const [preview, setPreview] = useState<BatchPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setScriptsText(text);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handlePreview() {
    if (!name.trim() || !templateId || !scriptsText.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await previewBatch({ name, template_id: templateId, scripts_text: scriptsText });
      setPreview(result);
      setStep("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not preview this batch.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const batch = await createBatch({ name, template_id: templateId, scripts_text: scriptsText });
      onCreated(batch);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this batch.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="batch-modal-backdrop" onClick={onClose}>
      <div className="batch-modal" onClick={(e) => e.stopPropagation()}>
        <div className="batch-modal-header">
          <h3>{step === "form" ? "New Batch" : "Preview Batch"}</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="batch-alert batch-alert-error">{error}</div>}

        {step === "form" ? (
          <>
            <label className="batch-field">
              <span>Batch name</span>
              <input
                type="text"
                placeholder="Emotional Stories August"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>

            <label className="batch-field">
              <span>Template (applied to every project)</span>
              {templatesError ? (
                <span className="batch-field-error">{templatesError}</span>
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

            <label className="batch-field">
              <div className="batch-field-row">
                <span>Scripts (separate multiple scripts with a line containing only ---)</span>
                <button className="btn btn-secondary batch-upload-btn" onClick={() => fileInputRef.current?.click()}>
                  <Upload size={13} />
                  Upload .txt
                </button>
                <input ref={fileInputRef} type="file" accept=".txt" hidden onChange={handleFileUpload} />
              </div>
              <textarea
                rows={10}
                placeholder={"First script.\n---\nSecond script.\n---\nThird script."}
                value={scriptsText}
                onChange={(e) => setScriptsText(e.target.value)}
              />
            </label>

            <div className="batch-modal-actions">
              <button className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handlePreview}
                disabled={busy || !name.trim() || !templateId || !scriptsText.trim()}
              >
                {busy ? <Loader2 size={14} className="spin" /> : null}
                Preview
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="batch-field-label">
              {preview?.script_count} script{preview?.script_count === 1 ? "" : "s"} will each become their own
              project, all using the "{templates.find((t) => t.id === templateId)?.name ?? templateId}" template.
            </p>
            <ul className="batch-preview-list">
              {preview?.items.map((item) => (
                <li key={item.index}>
                  <strong>{item.project_name}</strong>
                  <span>{item.script_preview}</span>
                </li>
              ))}
            </ul>
            <div className="batch-modal-actions">
              <button className="btn btn-secondary" onClick={() => setStep("form")}>
                Back
              </button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={busy}>
                {busy ? <Loader2 size={14} className="spin" /> : null}
                Create {preview?.script_count} Project{preview?.script_count === 1 ? "" : "s"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
