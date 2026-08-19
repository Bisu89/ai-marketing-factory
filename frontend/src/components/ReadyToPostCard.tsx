import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, FolderOpen, Loader2, RefreshCcw, Sparkles } from "lucide-react";
import { getLatestFactoryRun } from "../api/factory";
import { getProjectPackage, regenerateMetadata, regenerateThumbnail, setPackageOverrides } from "../api/package";
import { openVideoComposeJobFolder } from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import type { ReadyToPostPackage } from "../types/package";
import "./ReadyToPostCard.css";

const POLL_MS = 2000;
// Section 55: lightweight local work, but not instant -- a completed
// render job hands off here before the Factory's own PACKAGING stage
// (thumbnail extraction + metadata generation) has necessarily finished;
// this component polls briefly rather than assuming it's already done.
const POLL_TIMEOUT_MS = 60000;

interface ReadyToPostCardProps {
  projectId: number;
  jobId: number;
}

// Task 27 -- see docs/features/53-thumbnail-metadata-package.md section
// 44-47. Shown once a Factory-driven render's own PACKAGING stage has
// produced a complete package (thumbnail.jpg + metadata.json); a no-op,
// invisible card for a plain manual/upload-based render, which never has
// a package to show.
export function ReadyToPostCard({ projectId, jobId }: ReadyToPostCardProps) {
  const [pkg, setPkg] = useState<ReadyToPostPackage | null>(null);
  const [loaded, setLoaded] = useState(false);
  // Task 59 -- "Generate Full by AI": fetched independently of pkg (same
  // "each card fetches what it needs" shape this component already uses),
  // purely to show the real per-run image count/cost when this project
  // opted into AI-generated visuals. null for every "library" mode project
  // (the default) -- nothing renders in that case.
  const [aiVisualCost, setAiVisualCost] = useState<{ count: number; cost_usd: number } | null>(null);
  const [busy, setBusy] = useState<"thumbnail" | "metadata" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState<"title" | "description" | "hashtags" | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingDescription, setEditingDescription] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState("");
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAt = useRef(Date.now());

  const refresh = useCallback(async () => {
    try {
      const latest = await getProjectPackage(projectId);
      setPkg(latest);
    } catch {
      // No package yet (or a transient fetch error) -- render nothing,
      // same "convenience overlay, not load-bearing" reasoning as
      // ProductionProgress's own refresh().
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    startedAt.current = Date.now();
    refresh();
    getLatestFactoryRun(projectId)
      .then((run) => {
        if (run?.visual_generation_image_count != null && run.visual_generation_cost_usd != null) {
          setAiVisualCost({ count: run.visual_generation_image_count, cost_usd: run.visual_generation_cost_usd });
        } else {
          setAiVisualCost(null);
        }
      })
      .catch(() => setAiVisualCost(null));
  }, [refresh, projectId, jobId]);

  useEffect(() => {
    if (pkg != null && !pkg.is_complete && Date.now() - startedAt.current < POLL_TIMEOUT_MS) {
      pollRef.current = setTimeout(refresh, POLL_MS);
    }
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [pkg, refresh]);

  async function handleOpenFolder() {
    try {
      await openVideoComposeJobFolder(jobId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not open folder.");
    }
  }

  async function handleCopy(kind: "title" | "description" | "hashtags", text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      setTimeout(() => setCopied((current) => (current === kind ? null : current)), 1500);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not copy to clipboard.");
    }
  }

  async function handleRegenerateThumbnail() {
    setBusy("thumbnail");
    setActionError(null);
    try {
      await regenerateThumbnail(projectId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not regenerate thumbnail.");
    } finally {
      setBusy(null);
    }
  }

  async function handleRegenerateMetadata() {
    setBusy("metadata");
    setActionError(null);
    try {
      await regenerateMetadata(projectId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not regenerate metadata.");
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveTitle() {
    setActionError(null);
    try {
      await setPackageOverrides(projectId, titleDraft.trim() ? { title: titleDraft.trim() } : { clear_title: true });
      await regenerateMetadata(projectId);
      setEditingTitle(false);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not save title.");
    }
  }

  async function handleSaveDescription() {
    setActionError(null);
    try {
      await setPackageOverrides(
        projectId, descriptionDraft.trim() ? { description: descriptionDraft.trim() } : { clear_description: true },
      );
      await regenerateMetadata(projectId);
      setEditingDescription(false);
      await refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not save description.");
    }
  }

  if (!loaded || pkg == null || !pkg.is_complete) return null;

  return (
    <div className="rtp-card">
      <div className="rtp-header">
        <Check size={16} className="rtp-check" />
        <h3>Ready to Post</h3>
        {aiVisualCost && (
          <span className="rtp-ai-cost" title="Visuals generated by OpenAI for this video">
            <Sparkles size={13} />
            AI images: {aiVisualCost.count} (${aiVisualCost.cost_usd.toFixed(2)})
          </span>
        )}
      </div>

      <div className="rtp-body">
        {pkg.thumbnail_media_url && (
          <img className="rtp-thumbnail" src={mediaUrl(pkg.thumbnail_media_url)} alt="Video thumbnail" />
        )}
        <div className="rtp-fields">
          <div className="rtp-field">
            <div className="rtp-field-header">
              <span className="rtp-field-label">Title</span>
              <div className="rtp-field-actions">
                <button className="rtp-icon-btn" onClick={() => handleCopy("title", pkg.title ?? "")} title="Copy Title">
                  {copied === "title" ? <Check size={13} /> : <Copy size={13} />}
                </button>
                <button
                  className="rtp-icon-btn"
                  onClick={() => {
                    setTitleDraft(pkg.title ?? "");
                    setEditingTitle(true);
                  }}
                >
                  Edit
                </button>
              </div>
            </div>
            {editingTitle ? (
              <div className="rtp-edit-row">
                <input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
                <button className="btn btn-primary" onClick={handleSaveTitle}>
                  Save
                </button>
                <button className="btn btn-secondary" onClick={() => setEditingTitle(false)}>
                  Cancel
                </button>
              </div>
            ) : (
              <p className="rtp-field-value">{pkg.title}</p>
            )}
          </div>

          <div className="rtp-field">
            <div className="rtp-field-header">
              <span className="rtp-field-label">Description</span>
              <div className="rtp-field-actions">
                <button
                  className="rtp-icon-btn"
                  onClick={() => handleCopy("description", pkg.description ?? "")}
                  title="Copy Description"
                >
                  {copied === "description" ? <Check size={13} /> : <Copy size={13} />}
                </button>
                <button
                  className="rtp-icon-btn"
                  onClick={() => {
                    setDescriptionDraft(pkg.description ?? "");
                    setEditingDescription(true);
                  }}
                >
                  Edit
                </button>
              </div>
            </div>
            {editingDescription ? (
              <div className="rtp-edit-row">
                <textarea className="vf-textarea" value={descriptionDraft} onChange={(e) => setDescriptionDraft(e.target.value)} />
                <div className="rtp-row">
                  <button className="btn btn-primary" onClick={handleSaveDescription}>
                    Save
                  </button>
                  <button className="btn btn-secondary" onClick={() => setEditingDescription(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="rtp-field-value rtp-description">{pkg.description}</p>
            )}
          </div>

          <div className="rtp-field">
            <div className="rtp-field-header">
              <span className="rtp-field-label">Hashtags</span>
              <button
                className="rtp-icon-btn"
                onClick={() => handleCopy("hashtags", pkg.hashtags.join(" "))}
                title="Copy Hashtags"
              >
                {copied === "hashtags" ? <Check size={13} /> : <Copy size={13} />}
              </button>
            </div>
            <p className="rtp-field-value">{pkg.hashtags.join(" ")}</p>
          </div>
        </div>
      </div>

      <div className="rtp-row">
        <button className="btn btn-secondary" onClick={handleOpenFolder}>
          <FolderOpen size={14} />
          Open Folder
        </button>
        <button className="btn btn-secondary" onClick={handleRegenerateThumbnail} disabled={busy != null}>
          {busy === "thumbnail" ? <Loader2 size={14} className="spin" /> : <RefreshCcw size={14} />}
          Regenerate Thumbnail
        </button>
        <button className="btn btn-secondary" onClick={handleRegenerateMetadata} disabled={busy != null}>
          {busy === "metadata" ? <Loader2 size={14} className="spin" /> : <RefreshCcw size={14} />}
          Regenerate Metadata
        </button>
      </div>
      {actionError && <div className="rtp-alert">{actionError}</div>}
    </div>
  );
}
