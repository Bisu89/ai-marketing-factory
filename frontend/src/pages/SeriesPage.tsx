import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ListVideo, Loader2, Plus, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { createSeries, listSeries } from "../api/series";
import type { Series } from "../types/series";
import "./SeriesPage.css";

// Series (scoped-down "100-Day Series") -- a standing container (name +
// character/visual description) that independently-authored Projects
// attach to (see SeriesDetailPage.tsx), so their AI-generated images share
// one character description. Episodes are still each created exactly like
// today's existing "New Video" flow -- no AI-planned story arc here.

export function SeriesPage() {
  const navigate = useNavigate();
  const [series, setSeries] = useState<Series[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  async function refresh() {
    try {
      setLoadError(null);
      setSeries(await listSeries());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load series.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <PageHeader
        title="Series"
        subtitle="Group episodes under one character/visual description so their AI-generated images stay consistent -- each episode is still written and produced exactly like a normal video."
        actions={
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus size={14} />
            Create Series
          </button>
        }
      />

      {loadError && <div className="series-alert series-alert-error">{loadError}</div>}

      {series.length === 0 ? (
        <EmptyState
          icon={ListVideo}
          title="No series yet"
          description="Create a series to give a set of episodes one persistent character/visual description."
        />
      ) : (
        <div className="series-table-wrap">
          <table className="series-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Character / visual description</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr key={s.id} onClick={() => navigate(`/series/${s.id}`)} className="series-row-clickable">
                  <td>{s.name}</td>
                  <td>
                    <span className="series-description-preview">{s.character_description || "--"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateSeriesModal
          onClose={() => setCreateOpen(false)}
          onCreated={(s) => {
            setCreateOpen(false);
            navigate(`/series/${s.id}`);
          }}
        />
      )}
    </>
  );
}

function CreateSeriesModal({ onClose, onCreated }: { onClose: () => void; onCreated: (series: Series) => void }) {
  const [name, setName] = useState("");
  const [characterDescription, setCharacterDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const series = await createSeries({ name: name.trim(), character_description: characterDescription.trim() });
      onCreated(series);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this series.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="series-modal-backdrop" onClick={onClose}>
      <div className="series-modal" onClick={(e) => e.stopPropagation()}>
        <div className="series-modal-header">
          <h3>Create Series</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="series-alert series-alert-error">{error}</div>}

        <label className="series-field">
          <span>Series name</span>
          <input
            type="text"
            placeholder="100 Days to Rebuild My Life"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>

        <label className="series-field">
          <span>Character / visual description (optional)</span>
          <textarea
            rows={4}
            placeholder="male, 28, short messy hair, grey hoodie, average build"
            value={characterDescription}
            onChange={(e) => setCharacterDescription(e.target.value)}
          />
        </label>
        <p className="series-hint">
          Appended to every attached episode's own AI image-generation prompt, so episodes share a consistent look
          (style-level consistency -- not a guarantee every episode's images show an identical face).
        </p>

        <div className="series-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy || !name.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
