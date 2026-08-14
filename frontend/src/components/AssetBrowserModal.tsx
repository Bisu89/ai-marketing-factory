import { useEffect, useState } from "react";
import { AlertTriangle, ImageOff, Loader2, Music, Plus, Search, X } from "lucide-react";
import { getAsset, registerAsset, searchAssets, assetFileUrl } from "../api/asset";
import type { Asset, AssetType } from "../types/asset";
import "./AssetBrowserModal.css";

function filenameFromPath(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

interface AssetBrowserModalProps {
  assetType?: AssetType;
  initialQuery?: string;
  onSelect: (asset: Asset) => void;
  onClose: () => void;
}

export function AssetBrowserModal({ assetType = "image", initialQuery, onSelect, onClose }: AssetBrowserModalProps) {
  const [query, setQuery] = useState(initialQuery ?? "");
  const [results, setResults] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [newPath, setNewPath] = useState("");
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  async function runSearch(q: string) {
    setLoading(true);
    setSearchError(null);
    try {
      const assets = await searchAssets(q || undefined, assetType);
      setResults(assets);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Could not search assets.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runSearch(query);
    // Suggested-assets seed: search once on open using the beat's own
    // visual_hint as the query (see docs/features/32-asset-library-beat-visual-assignment.md)
    // -- ordinary keyword search, not a separate "suggestions" system.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRegisterNew() {
    const path = newPath.trim();
    if (!path) return;
    setRegistering(true);
    setRegisterError(null);
    try {
      const asset = await registerAsset({ filename: filenameFromPath(path), path, type: assetType });
      setResults((prev) => [asset, ...prev]);
      setSelectedId(asset.id);
      setNewPath("");
    } catch (err) {
      // A path already registered isn't really an error for this flow --
      // the user almost certainly means "use that one." Look it up instead
      // of just failing (same fallback used by the older register flow).
      try {
        const matches = await searchAssets(filenameFromPath(path));
        const existing = matches.find((a) => a.path.toLowerCase() === path.toLowerCase());
        if (existing) {
          setResults((prev) => (prev.some((a) => a.id === existing.id) ? prev : [existing, ...prev]));
          setSelectedId(existing.id);
          setNewPath("");
          return;
        }
      } catch {
        // Fall through to reporting the original registration error below.
      }
      setRegisterError(err instanceof Error ? err.message : "Could not register asset.");
    } finally {
      setRegistering(false);
    }
  }

  async function handleConfirmSelect() {
    if (selectedId == null) return;
    const known = results.find((a) => a.id === selectedId);
    if (known) {
      onSelect(known);
      return;
    }
    // Selected before this run's search results loaded it (e.g. picked from
    // a prior render) -- re-fetch by id rather than trusting stale local data.
    try {
      onSelect(await getAsset(selectedId));
    } catch {
      // Nothing to select anymore; leave the modal open so the user can pick again.
    }
  }

  return (
    <div className="asset-modal-overlay" onClick={onClose}>
      <div className="asset-modal" onClick={(e) => e.stopPropagation()}>
        <div className="asset-modal-header">
          <span>Choose {assetType}</span>
          <button className="asset-modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form
          className="asset-modal-search"
          onSubmit={(e) => {
            e.preventDefault();
            runSearch(query);
          }}
        >
          <Search size={14} />
          <input
            type="text"
            placeholder="Search assets (tags, filename)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary">
            Search
          </button>
        </form>

        <div className="asset-modal-register">
          <input
            type="text"
            placeholder={`Or paste a new ${assetType} file path to register it...`}
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
          />
          <button className="btn btn-secondary" onClick={handleRegisterNew} disabled={!newPath.trim() || registering}>
            {registering ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
            Register
          </button>
        </div>
        {registerError && (
          <div className="asset-modal-error">
            <AlertTriangle size={13} /> {registerError}
          </div>
        )}

        <div className="asset-modal-grid-wrap">
          {loading ? (
            <div className="asset-modal-status">
              <Loader2 size={18} className="spin" />
            </div>
          ) : searchError ? (
            <div className="asset-modal-status asset-modal-error">
              <AlertTriangle size={16} /> {searchError}
            </div>
          ) : results.length === 0 ? (
            <div className="asset-modal-status">No {assetType} assets found.</div>
          ) : (
            <div className="asset-modal-grid">
              {results.map((asset) => (
                <button
                  key={asset.id}
                  className={`asset-modal-tile${selectedId === asset.id ? " selected" : ""}${!asset.is_ready ? " unavailable" : ""}`}
                  onClick={() => setSelectedId(asset.id)}
                  title={asset.filename}
                  disabled={!asset.is_ready}
                >
                  {!asset.is_ready ? (
                    <div className="asset-modal-tile-missing">
                      <ImageOff size={20} />
                    </div>
                  ) : assetType === "audio" ? (
                    <div className="asset-modal-tile-audio">
                      <Music size={22} />
                    </div>
                  ) : (
                    <img src={assetFileUrl(asset.id)} alt={asset.filename} loading="lazy" />
                  )}
                  <span className="asset-modal-tile-name">{asset.filename}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="asset-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={selectedId == null} onClick={handleConfirmSelect}>
            Select
          </button>
        </div>
      </div>
    </div>
  );
}
