import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Ban,
  FileImage,
  FolderInput,
  ImageOff,
  Loader2,
  Music,
  Plus,
  RefreshCw,
  Trash2,
  Video,
  X,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import {
  assetFileUrl,
  assetThumbnailUrl,
  cancelAssetImportJob,
  deleteAsset,
  getAssetImportJob,
  importAssets,
  rescanAssets,
  searchAssets,
} from "../api/asset";
import type { Asset, AssetImportJob, AssetOrientation, RescanResult } from "../types/asset";
import "./AssetLibraryPage.css";

const ORIENTATIONS: AssetOrientation[] = ["PORTRAIT", "LANDSCAPE", "SQUARE"];
const SUITABILITY_LABEL: Record<string, string> = {
  EXCELLENT: "Excellent for 9:16",
  GOOD: "Good for 9:16",
  CROP_REQUIRED: "Needs cropping",
  LOW_RESOLUTION: "Low resolution",
};

function formatSize(bytes: number | null): string {
  if (!bytes) return "--";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AssetLibraryPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [query, setQuery] = useState("");
  const [assetType, setAssetType] = useState("");
  const [orientation, setOrientation] = useState("");
  const [category, setCategory] = useState("");
  const [emotion, setEmotion] = useState("");
  const [missingOnly, setMissingOnly] = useState(false);

  const [selected, setSelected] = useState<Asset | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [job, setJob] = useState<AssetImportJob | null>(null);
  const [rescanBusy, setRescanBusy] = useState(false);
  const [rescanResult, setRescanResult] = useState<RescanResult | null>(null);

  async function refresh() {
    setLoading(true);
    setLoadError(null);
    try {
      const results = await searchAssets(query || undefined, assetType || undefined, {
        orientation: orientation || undefined,
        category: category || undefined,
        emotion: emotion || undefined,
        missingOnly,
      });
      setAssets(results);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load the asset library.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetType, orientation, category, emotion, missingOnly]);

  // Poll the active import job until it reaches a terminal status.
  useEffect(() => {
    if (!job || !["QUEUED", "RUNNING"].includes(job.status)) return;
    const interval = setInterval(async () => {
      try {
        const updated = await getAssetImportJob(job.id);
        setJob(updated);
        if (!["QUEUED", "RUNNING"].includes(updated.status)) {
          refresh();
        }
      } catch {
        // Transient poll failure -- try again next tick.
      }
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.id, job?.status]);

  async function handleCancelImport() {
    if (!job) return;
    try {
      const updated = await cancelAssetImportJob(job.id);
      setJob(updated);
    } catch {
      // Ignore -- the poller will pick up the real state shortly.
    }
  }

  async function handleRescan() {
    setRescanBusy(true);
    setRescanResult(null);
    try {
      const result = await rescanAssets();
      setRescanResult(result);
      refresh();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not rescan the library.");
    } finally {
      setRescanBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Asset Library"
        subtitle="A local, reusable pool of visual assets for the Video Factory -- $0 to build, $0 to search."
        actions={
          <div className="al-header-actions">
            <button className="btn btn-secondary" onClick={handleRescan} disabled={rescanBusy}>
              {rescanBusy ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
              Re-scan Library
            </button>
            <button className="btn btn-primary" onClick={() => setImportOpen(true)}>
              <Plus size={14} />
              Add Assets
            </button>
          </div>
        }
      />

      {rescanResult && (
        <div className="al-alert al-alert-info">
          Re-scan complete -- checked {rescanResult.checked}, now missing {rescanResult.now_missing}, restored{" "}
          {rescanResult.now_active}, now invalid {rescanResult.now_invalid}, unchanged {rescanResult.unchanged}.
        </div>
      )}

      {job && (
        <ImportProgressBanner job={job} onCancel={handleCancelImport} onDismiss={() => setJob(null)} />
      )}

      <div className="al-filters">
        <form
          className="al-search"
          onSubmit={(e) => {
            e.preventDefault();
            refresh();
          }}
        >
          <input
            type="text"
            placeholder="Search tags, filename..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary">
            Search
          </button>
        </form>

        <select value={assetType} onChange={(e) => setAssetType(e.target.value)}>
          <option value="">All types</option>
          <option value="image">Image</option>
          <option value="video">Video</option>
          <option value="audio">Audio</option>
        </select>

        <select value={orientation} onChange={(e) => setOrientation(e.target.value)}>
          <option value="">All orientations</option>
          {ORIENTATIONS.map((o) => (
            <option key={o} value={o}>
              {o.charAt(0) + o.slice(1).toLowerCase()}
            </option>
          ))}
        </select>

        <input
          type="text"
          className="al-filter-text"
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          onBlur={refresh}
        />
        <input
          type="text"
          className="al-filter-text"
          placeholder="Emotion"
          value={emotion}
          onChange={(e) => setEmotion(e.target.value)}
          onBlur={refresh}
        />

        <label className="al-missing-toggle">
          <input type="checkbox" checked={missingOnly} onChange={(e) => setMissingOnly(e.target.checked)} />
          Missing only
        </label>
      </div>

      {loadError && (
        <div className="al-alert al-alert-error">
          <AlertTriangle size={14} /> {loadError}
        </div>
      )}

      {loading ? (
        <div className="al-status">
          <Loader2 size={20} className="spin" />
        </div>
      ) : assets.length === 0 ? (
        <EmptyState
          icon={FileImage}
          title="No assets yet"
          description="Add individual files or import a whole folder to build a local, reusable visual library."
        />
      ) : (
        <div className="al-grid">
          {assets.map((asset) => (
            <AssetTile key={asset.id} asset={asset} onClick={() => setSelected(asset)} />
          ))}
        </div>
      )}

      {selected && (
        <AssetDetailPanel
          asset={selected}
          onClose={() => setSelected(null)}
          onDeleted={() => {
            setSelected(null);
            refresh();
          }}
        />
      )}

      {importOpen && (
        <ImportModal
          onClose={() => setImportOpen(false)}
          onStarted={(newJob) => {
            setJob(newJob);
            setImportOpen(false);
          }}
        />
      )}
    </>
  );
}

function AssetTile({ asset, onClick }: { asset: Asset; onClick: () => void }) {
  const broken = asset.status === "MISSING" || asset.status === "INVALID";
  return (
    <button className={`al-tile${broken ? " al-tile-broken" : ""}`} onClick={onClick} title={asset.filename}>
      {broken ? (
        <div className="al-tile-icon">
          <ImageOff size={22} />
        </div>
      ) : asset.type === "audio" ? (
        <div className="al-tile-icon">
          <Music size={22} />
        </div>
      ) : (
        <img
          src={asset.thumbnail_path ? assetThumbnailUrl(asset.id) : assetFileUrl(asset.id)}
          alt={asset.filename}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      {asset.type === "video" && (
        <span className="al-tile-video-badge">
          <Video size={11} />
        </span>
      )}
      <span className="al-tile-name">{asset.filename}</span>
    </button>
  );
}

function AssetDetailPanel({
  asset,
  onClose,
  onDeleted,
}: {
  asset: Asset;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    if (deleting) return;
    if (
      !window.confirm(
        `Remove "${asset.filename}" from the Asset Library? The file itself stays on disk -- this only unregisters it (any beat currently using it will show a broken reference).`
      )
    ) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAsset(asset.id);
      onDeleted();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete this asset.");
      setDeleting(false);
    }
  }

  return (
    <div className="al-modal-backdrop" onClick={onClose}>
      <div className="al-detail-panel" onClick={(e) => e.stopPropagation()}>
        <div className="al-modal-header">
          <h3>{asset.filename}</h3>
          <div className="al-modal-header-actions">
            <button className="btn btn-secondary al-delete-btn" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
              Delete
            </button>
            <button className="btn btn-icon" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>

        {deleteError && (
          <div className="al-alert al-alert-error">
            <AlertTriangle size={14} /> {deleteError}
          </div>
        )}

        {asset.type !== "audio" && asset.status === "ACTIVE" && (
          <img className="al-detail-preview" src={assetFileUrl(asset.id)} alt={asset.filename} />
        )}

        <dl className="al-detail-list">
          <dt>Resolution</dt>
          <dd>{asset.width && asset.height ? `${asset.width} × ${asset.height}` : "--"}</dd>

          <dt>Orientation</dt>
          <dd>{asset.orientation ?? "--"}</dd>

          {asset.portrait_suitability && (
            <>
              <dt>9:16 suitability</dt>
              <dd>{SUITABILITY_LABEL[asset.portrait_suitability] ?? asset.portrait_suitability}</dd>
            </>
          )}

          <dt>Tags</dt>
          <dd>{asset.tags.length > 0 ? asset.tags.join(", ") : "--"}</dd>

          <dt>Category</dt>
          <dd>{asset.category ?? "--"}</dd>

          <dt>Emotion</dt>
          <dd>{asset.emotion ?? "--"}</dd>

          <dt>Source</dt>
          <dd>{asset.source}</dd>

          <dt>Status</dt>
          <dd className={`al-status-${asset.status}`}>{asset.status}</dd>

          <dt>File size</dt>
          <dd>{formatSize(asset.filesize_bytes)}</dd>

          <dt>Path</dt>
          <dd className="al-detail-path">{asset.path}</dd>
        </dl>
      </div>
    </div>
  );
}

function ImportProgressBanner({
  job,
  onCancel,
  onDismiss,
}: {
  job: AssetImportJob;
  onCancel: () => void;
  onDismiss: () => void;
}) {
  const active = job.status === "QUEUED" || job.status === "RUNNING";
  return (
    <div className="al-import-banner">
      {active ? (
        <>
          <Loader2 size={16} className="spin" />
          <span>
            Importing{job.current_file ? ` -- ${job.current_file.split(/[\\/]/).pop()}` : "..."} ({job.processed_files}/
            {job.total_files})
          </span>
          <span className="al-import-counts">
            Imported {job.imported_count} &bull; Duplicates {job.duplicate_count} &bull; Failed {job.failed_count}
          </span>
          <button className="btn btn-secondary al-import-cancel" onClick={onCancel}>
            <Ban size={13} />
            Cancel
          </button>
        </>
      ) : (
        <>
          <span>
            Import {job.status === "COMPLETED" ? "complete" : job.status.toLowerCase()} -- {job.imported_count}{" "}
            imported, {job.duplicate_count} duplicates, {job.failed_count} failed
            {job.duration_seconds != null ? ` in ${job.duration_seconds.toFixed(1)}s` : ""}.
          </span>
          {job.failed_files.length > 0 && (
            <span className="al-import-counts">
              First failure: {job.failed_files[0].path.split(/[\\/]/).pop()} -- {job.failed_files[0].reason}
            </span>
          )}
          <button className="btn btn-secondary al-import-cancel" onClick={onDismiss}>
            Done
          </button>
        </>
      )}
    </div>
  );
}

function ImportModal({ onClose, onStarted }: { onClose: () => void; onStarted: (job: AssetImportJob) => void }) {
  const [mode, setMode] = useState<"files" | "folder">("folder");
  const [pathsText, setPathsText] = useState("");
  const [folder, setFolder] = useState("");
  const [recursive, setRecursive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const job =
        mode === "folder"
          ? await importAssets({ folder: folder.trim(), recursive })
          : await importAssets({
              paths: pathsText
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean),
            });
      onStarted(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the import.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="al-modal-backdrop" onClick={onClose}>
      <div className="al-import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="al-modal-header">
          <h3>Add Assets</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="al-mode-tabs">
          <button className={mode === "folder" ? "active" : ""} onClick={() => setMode("folder")}>
            <FolderInput size={14} />
            Import Folder
          </button>
          <button className={mode === "files" ? "active" : ""} onClick={() => setMode("files")}>
            <Plus size={14} />
            Add Files
          </button>
        </div>

        {error && (
          <div className="al-alert al-alert-error">
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {mode === "folder" ? (
          <>
            <label className="al-field">
              <span>Folder path</span>
              <input
                type="text"
                placeholder="C:\VideoAssets\EmotionalStories"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
              />
            </label>
            <label className="al-checkbox-field">
              <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />
              Include subfolders
            </label>
          </>
        ) : (
          <label className="al-field">
            <div className="al-field-row">
              <span>File paths (one per line)</span>
              <button
                className="btn btn-secondary al-upload-btn"
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                Browse...
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                hidden
                onChange={(e) => {
                  // Browser file pickers don't expose a real filesystem
                  // path for security reasons -- only the filename is
                  // usable here, so this just seeds the textarea for the
                  // user to complete with real local paths, matching this
                  // app's existing "paste a path" convention elsewhere
                  // (see AssetBrowserModal's own "paste a file path"
                  // input) rather than pretending to support true native
                  // file upload.
                  const names = Array.from(e.target.files ?? []).map((f) => f.name);
                  if (names.length > 0) setPathsText((prev) => [prev, ...names].filter(Boolean).join("\n"));
                }}
              />
            </div>
            <textarea
              rows={8}
              placeholder={"C:\\VideoAssets\\photo1.jpg\nC:\\VideoAssets\\photo2.jpg"}
              value={pathsText}
              onChange={(e) => setPathsText(e.target.value)}
            />
          </label>
        )}

        <div className="al-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={busy || (mode === "folder" ? !folder.trim() : !pathsText.trim())}
          >
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Start Import
          </button>
        </div>
      </div>
    </div>
  );
}
