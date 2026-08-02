import { useEffect, useState } from "react";
import { ArrowUp, Folder, X } from "lucide-react";
import { browseFolders } from "../api/settings";
import type { FolderEntry } from "../types/settings";
import "./FolderBrowserModal.css";

interface FolderBrowserModalProps {
  initialPath?: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

export function FolderBrowserModal({ initialPath, onSelect, onClose }: FolderBrowserModalProps) {
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [folders, setFolders] = useState<FolderEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function navigate(path?: string) {
    setError(null);
    try {
      const result = await browseFolders(path);
      setCurrentPath(result.current_path);
      setParentPath(result.parent_path);
      setFolders(result.folders);
    } catch {
      setError("Không duyệt được thư mục này.");
    }
  }

  useEffect(() => {
    navigate(initialPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="folder-modal-overlay" onClick={onClose}>
      <div className="folder-modal" onClick={(e) => e.stopPropagation()}>
        <div className="folder-modal-header">
          <span>Chọn thư mục</span>
          <button className="folder-modal-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="folder-modal-path">{currentPath ?? "Chọn ổ đĩa"}</div>

        {error && <div className="folder-modal-error">{error}</div>}

        <div className="folder-modal-list">
          {parentPath && (
            <button className="folder-modal-item" onClick={() => navigate(parentPath)}>
              <ArrowUp size={16} />
              Lên thư mục cha
            </button>
          )}
          {folders.map((folder) => (
            <button key={folder.path} className="folder-modal-item" onClick={() => navigate(folder.path)}>
              <Folder size={16} />
              {folder.name}
            </button>
          ))}
        </div>

        <div className="folder-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Huỷ
          </button>
          <button
            className="btn btn-primary"
            disabled={!currentPath}
            onClick={() => currentPath && onSelect(currentPath)}
          >
            Chọn thư mục này
          </button>
        </div>
      </div>
    </div>
  );
}
