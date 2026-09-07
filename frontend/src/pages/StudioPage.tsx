import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clapperboard, Loader2, Plus, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { createStory, listStories } from "../api/story";
import { STORY_MODES } from "../types/story";
import type { CreateStoryRequest, Story, StoryMode } from "../types/story";
import "./StudioPage.css";

// AI Storytelling Studio -- audio-first long-form / Shorts story production.
// This page is the planning surface: create a Story, run the planning
// pipeline (idea -> bible -> chapters -> scenes -> scene classification),
// review the Scene Director's STILL / STILL_WITH_MOTION / AI_VIDEO calls
// and the pre-flight cost estimate. Compiling to a renderable video is a
// later phase.

const MODE_LABEL: Record<StoryMode, string> = {
  STORY: "Original story",
  HISTORY: "History documentary",
  EDUCATION: "Educational",
};

export function StudioPage() {
  const navigate = useNavigate();
  const [stories, setStories] = useState<Story[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  async function refresh() {
    try {
      setLoadError(null);
      setStories(await listStories());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load stories.");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <PageHeader
        title="Storytelling Studio"
        subtitle="Plan an audio-first story: the pipeline drafts the bible, characters, chapters and scenes, then the Scene Director decides which scenes are stills, which get motion, and which are worth an AI-video clip -- with a cost estimate before anything is generated."
        actions={
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus size={14} />
            New Story
          </button>
        }
      />

      {loadError && <div className="studio-alert studio-alert-error">{loadError}</div>}

      {loaded && stories.length === 0 ? (
        <EmptyState
          icon={Clapperboard}
          title="No stories yet"
          description="Create a story, give it a logline, and run the planning pipeline."
        />
      ) : (
        <div className="studio-table-wrap">
          <table className="studio-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Budget</th>
              </tr>
            </thead>
            <tbody>
              {stories.map((s) => (
                <tr key={s.id} onClick={() => navigate(`/studio/${s.id}`)} className="studio-row-clickable">
                  <td>
                    <div className="studio-story-title">{s.title}</div>
                    {s.logline && <div className="studio-story-logline">{s.logline}</div>}
                  </td>
                  <td>{MODE_LABEL[s.mode] ?? s.mode}</td>
                  <td>
                    <span className="studio-status-pill">{s.status}</span>
                  </td>
                  <td>{s.budget_usd != null ? `$${s.budget_usd.toFixed(2)}` : "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateStoryModal
          onClose={() => setCreateOpen(false)}
          onCreated={(s) => {
            setCreateOpen(false);
            navigate(`/studio/${s.id}`);
          }}
        />
      )}
    </>
  );
}

function CreateStoryModal({ onClose, onCreated }: { onClose: () => void; onCreated: (story: Story) => void }) {
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<StoryMode>("STORY");
  const [logline, setLogline] = useState("");
  const [genre, setGenre] = useState("");
  const [budget, setBudget] = useState("");
  const [referenceNotes, setReferenceNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!title.trim() || busy) return;
    setBusy(true);
    setError(null);
    const payload: CreateStoryRequest = {
      title: title.trim(),
      mode,
      logline: logline.trim() || null,
      genre: genre.trim() || null,
      budget_usd: budget.trim() ? Number(budget) : null,
      reference_notes: referenceNotes.trim() || null,
    };
    try {
      onCreated(await createStory(payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this story.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="studio-modal-backdrop" onClick={onClose}>
      <div className="studio-modal" onClick={(e) => e.stopPropagation()}>
        <div className="studio-modal-header">
          <h3>New Story</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && <div className="studio-alert studio-alert-error">{error}</div>}

        <label className="studio-field">
          <span>Title</span>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="The Siege Courier" />
        </label>

        <label className="studio-field">
          <span>Mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as StoryMode)}>
            {STORY_MODES.map((m) => (
              <option key={m} value={m}>
                {MODE_LABEL[m]}
              </option>
            ))}
          </select>
        </label>

        <label className="studio-field">
          <span>Logline</span>
          <textarea
            rows={2}
            value={logline}
            onChange={(e) => setLogline(e.target.value)}
            placeholder="A courier must cross a besieged city before dawn to deliver a surrender order."
          />
        </label>

        <div className="studio-field-row">
          <label className="studio-field">
            <span>Genre</span>
            <input type="text" value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="thriller" />
          </label>
          <label className="studio-field">
            <span>Budget cap (USD, optional)</span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="5.00"
            />
          </label>
        </div>

        {mode !== "STORY" && (
          <label className="studio-field">
            <span>Reference notes {mode === "HISTORY" ? "(the only source for factual claims)" : ""}</span>
            <textarea
              rows={4}
              value={referenceNotes}
              onChange={(e) => setReferenceNotes(e.target.value)}
              placeholder="Paste the facts / sources this story must stay faithful to."
            />
          </label>
        )}

        <div className="studio-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={busy || !title.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
