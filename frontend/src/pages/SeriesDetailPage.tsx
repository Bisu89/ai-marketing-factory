import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2, Pencil, Plus, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { NewVideoModal } from "../components/NewVideoModal";
import { getSeries, listSeriesProjects, updateSeries } from "../api/series";
import type { Series, SeriesProjectSummary } from "../types/series";
import "./SeriesPage.css";

export function SeriesDetailPage() {
  const { seriesId } = useParams<{ seriesId: string }>();
  const navigate = useNavigate();
  const id = Number(seriesId);

  const [series, setSeries] = useState<Series | null>(null);
  const [episodes, setEpisodes] = useState<SeriesProjectSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [newEpisodeOpen, setNewEpisodeOpen] = useState(false);

  async function refresh() {
    try {
      setLoadError(null);
      const [s, eps] = await Promise.all([getSeries(id), listSeriesProjects(id)]);
      setSeries(s);
      setEpisodes(eps);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load this series.");
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loadError) {
    return (
      <>
        <PageHeader title="Series" />
        <div className="series-alert series-alert-error">{loadError}</div>
      </>
    );
  }

  if (!series) {
    return (
      <>
        <PageHeader title="Series" />
        <Loader2 size={20} className="spin" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={series.name}
        subtitle={`${episodes.length} episode${episodes.length === 1 ? "" : "s"}`}
        actions={
          <button className="btn btn-primary" onClick={() => setNewEpisodeOpen(true)}>
            <Plus size={14} />
            New Episode
          </button>
        }
      />

      <div className="series-detail-header">
        <div className="series-detail-header-row">
          <strong>Character / visual description</strong>
          <button className="btn btn-icon" onClick={() => setEditOpen(true)} title="Edit">
            <Pencil size={14} />
          </button>
        </div>
        <p className="series-detail-description">{series.character_description || "(none set)"}</p>
      </div>

      {episodes.length === 0 ? (
        <EmptyState
          icon={Plus}
          title="No episodes yet"
          description="Click 'New Episode' to write and produce the first episode of this series."
        />
      ) : (
        <div className="series-table-wrap">
          <table className="series-table">
            <thead>
              <tr>
                <th>Episode</th>
                <th>Name</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {episodes.map((ep) => (
                <tr
                  key={ep.id}
                  onClick={() => navigate(`/video-factory?project=${ep.id}`)}
                  className="series-row-clickable"
                >
                  <td>
                    <span className="series-episode-number">{ep.episode_number ?? "--"}</span>
                  </td>
                  <td>{ep.name}</td>
                  <td>{ep.render_job_id != null ? "Rendered" : "Not rendered yet"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {newEpisodeOpen && (
        <NewVideoModal
          seriesId={series.id}
          onClose={() => {
            setNewEpisodeOpen(false);
            refresh();
          }}
        />
      )}

      {editOpen && (
        <EditSeriesModal
          series={series}
          onClose={() => setEditOpen(false)}
          onSaved={(updated) => {
            setSeries(updated);
            setEditOpen(false);
          }}
        />
      )}
    </>
  );
}

function EditSeriesModal({
  series,
  onClose,
  onSaved,
}: {
  series: Series;
  onClose: () => void;
  onSaved: (series: Series) => void;
}) {
  const [name, setName] = useState(series.name);
  const [characterDescription, setCharacterDescription] = useState(series.character_description);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateSeries(series.id, {
        name: name.trim(),
        character_description: characterDescription.trim(),
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this series.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="series-modal-backdrop" onClick={onClose}>
      <div className="series-modal" onClick={(e) => e.stopPropagation()}>
        <div className="series-modal-header">
          <h3>Edit Series</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="series-alert series-alert-error">{error}</div>}

        <label className="series-field">
          <span>Series name</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <label className="series-field">
          <span>Character / visual description</span>
          <textarea rows={4} value={characterDescription} onChange={(e) => setCharacterDescription(e.target.value)} />
        </label>
        <p className="series-hint">
          Only affects new episodes attached from now on -- already-attached episodes keep the description they were
          created with.
        </p>

        <div className="series-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={busy || !name.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
