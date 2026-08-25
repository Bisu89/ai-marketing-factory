import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, FolderOpen, Loader2, RefreshCcw, Sparkles } from "lucide-react";
import { getLatestFactoryRun } from "../api/factory";
import { getProjectPackage, regenerateMetadata, regenerateThumbnail, setPackageOverrides } from "../api/package";
import { openVideoComposeJobFolder } from "../api/videoComposer";
import { mediaUrl } from "../api/client";
import { isActiveFactoryRun } from "../types/factory";
import type { FactoryRun } from "../types/factory";
import type { ReadyToPostPackage } from "../types/package";
import "./ReadyToPostCard.css";

const POLL_MS = 2000;
// Real user report: the page looked frozen right after a render finished
// -- nothing appeared until a manual page refresh. Root cause: this used
// to hard-stop polling after a fixed POLL_TIMEOUT_MS (60s), and while
// `!pkg.is_complete` this component returned null the entire time --
// rendered nothing at all, no "still working" indicator. PACKAGING
// generates up to thumbnail_candidate_count (6 by default) thumbnail
// candidates and, when "AI-write title/description/thumbnail text" is
// enabled, makes a real billed LLM call -- easily over a minute combined
// on a real machine. Once the old timeout passed, the polling useEffect
// below simply stopped scheduling itself, forever, with no visible sign
// anything had happened -- indistinguishable from "stuck" even though
// PACKAGING was still working fine in the background (a fresh page load
// resets `startedAt`, which is why F5 "fixed" it). Fixed two ways: this
// component now polls indefinitely (see the effect below) rather than
// giving up, and shows a visible "still preparing" card the whole time
// instead of silent nothing (see the render logic below). This constant
// now only controls when that card's text switches from a plain "preparing"
// message to a "taking longer than usual" one -- it no longer stops anything.
const PREPARING_HINT_DELAY_MS = 20000;

// A package that's incomplete only ever finishes on its own while the
// project's own FactoryRun is still actively working (PACKAGING/FINAL_QA)
// -- once that run reaches a terminal status (COMPLETED/FAILED/CANCELLED/
// etc), PACKAGING has already been attempted and either produced a package
// or didn't (e.g. the render's output file is missing on disk -- see
// generate_project_package's own "not an error" early return), and nothing
// further will ever change without a real user action (Retry, a fresh
// render). No FactoryRun at all (null) means a plain manual/upload-based
// render, which never had packaging to begin with. Both of those must fall
// back to rendering nothing (this component's original, correct behavior)
// rather than the "preparing" card below staying up forever and lying
// about still being in progress.
function packagingIsGenuinelyInProgress(run: FactoryRun | null): boolean {
  return run != null && isActiveFactoryRun(run.status);
}

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
  // See packagingIsGenuinelyInProgress above -- fetched alongside pkg on
  // every poll tick (not just once on mount) so it stays current as the
  // run actually progresses through PACKAGING -> FINAL_QA -> COMPLETED.
  const [run, setRun] = useState<FactoryRun | null>(null);
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
    try {
      const latestRun = await getLatestFactoryRun(projectId);
      setRun(latestRun);
      if (latestRun?.visual_generation_image_count != null && latestRun.visual_generation_cost_usd != null) {
        setAiVisualCost({ count: latestRun.visual_generation_image_count, cost_usd: latestRun.visual_generation_cost_usd });
      } else {
        setAiVisualCost(null);
      }
    } catch {
      // No FactoryRun for this project (plain manual/upload-based render)
      // -- see packagingIsGenuinelyInProgress above.
      setRun(null);
      setAiVisualCost(null);
    }
  }, [projectId]);

  useEffect(() => {
    startedAt.current = Date.now();
    refresh();
  }, [refresh, projectId, jobId]);

  useEffect(() => {
    if (pkg != null && !pkg.is_complete && packagingIsGenuinelyInProgress(run)) {
      pollRef.current = setTimeout(refresh, POLL_MS);
    }
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [pkg, run, refresh]);

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

  if (!loaded || pkg == null) return null;

  if (!pkg.is_complete && packagingIsGenuinelyInProgress(run)) {
    const takingAWhile = Date.now() - startedAt.current >= PREPARING_HINT_DELAY_MS;
    return (
      <div className="rtp-card rtp-card--preparing">
        <div className="rtp-header">
          <Loader2 size={16} className="spin" />
          <h3>Preparing Title, Description &amp; Thumbnail...</h3>
        </div>
        <p className="rtp-preparing-hint">
          {takingAWhile
            ? "Taking a bit longer than usual -- still working, no need to refresh."
            : "This usually only takes a few seconds."}
        </p>
      </div>
    );
  }

  // Incomplete, and packaging isn't (or is no longer) actively working on
  // it -- see packagingIsGenuinelyInProgress above. Nothing to show.
  if (!pkg.is_complete) return null;

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
