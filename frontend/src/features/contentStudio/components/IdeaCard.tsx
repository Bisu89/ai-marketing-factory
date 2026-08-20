import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";
import type { EmotionOut } from "../../library/types";
import type { Idea, IdeaStatus, IdeaUpdateInput } from "../types";
import "./IdeaCard.css";

const STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Nháp",
  approved: "Đã duyệt",
  rejected: "Từ chối",
  used: "Đã dùng",
};

interface IdeaCardProps {
  idea: Idea;
  pillarName: string;
  formatName: string;
  emotions: EmotionOut[];
  selected: boolean;
  onToggleSelect: (id: number) => void;
  onSave: (id: number, patch: IdeaUpdateInput) => Promise<void>;
  onDelete: (id: number) => void;
  deleting: boolean;
}

export function IdeaCard({
  idea,
  pillarName,
  formatName,
  emotions,
  selected,
  onToggleSelect,
  onSave,
  onDelete,
  deleting,
}: IdeaCardProps) {
  const [title, setTitle] = useState(idea.title);
  const [premise, setPremise] = useState(idea.premise ?? "");
  const [emotionId, setEmotionId] = useState<string>(idea.target_emotion_id?.toString() ?? "");
  const [commercialIntent, setCommercialIntent] = useState(idea.commercial_intent ?? "");
  const [score, setScore] = useState<string>(idea.score?.toString() ?? "");
  const [status, setStatus] = useState<IdeaStatus>(idea.status);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    title !== idea.title ||
    premise !== (idea.premise ?? "") ||
    emotionId !== (idea.target_emotion_id?.toString() ?? "") ||
    commercialIntent !== (idea.commercial_intent ?? "") ||
    score !== (idea.score?.toString() ?? "");

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await onSave(idea.id, {
        title,
        premise,
        target_emotion_id: emotionId ? Number(emotionId) : undefined,
        commercial_intent: commercialIntent,
        score: score ? Number(score) : undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được ý tưởng.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(next: IdeaStatus) {
    setStatus(next);
    setError(null);
    try {
      await onSave(idea.id, { status: next });
    } catch (err) {
      setStatus(idea.status);
      setError(err instanceof Error ? err.message : "Không đổi được trạng thái.");
    }
  }

  return (
    <div className={`idea-card idea-card--${idea.status}${selected ? " idea-card--selected" : ""}`}>
      <div className="idea-card-top">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(idea.id)}
          aria-label="Chọn ý tưởng"
        />
        <input
          className="idea-card-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Tiêu đề ý tưởng"
        />
        <select
          className="idea-card-status-select"
          value={status}
          onChange={(e) => handleStatusChange(e.target.value as IdeaStatus)}
        >
          {(Object.keys(STATUS_LABELS) as IdeaStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <button
          className="btn btn-secondary idea-card-delete"
          onClick={() => onDelete(idea.id)}
          disabled={deleting}
          aria-label="Xoá ý tưởng"
        >
          {deleting ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
        </button>
      </div>

      <div className="idea-card-meta">
        <span className="idea-card-badge">{pillarName}</span>
        <span className="idea-card-badge">{formatName}</span>
      </div>

      <textarea
        className="idea-card-premise"
        rows={2}
        value={premise}
        onChange={(e) => setPremise(e.target.value)}
        placeholder="Premise / tóm tắt nội dung..."
      />

      <div className="idea-card-fields">
        <label>
          <span>Cảm xúc mục tiêu</span>
          <select value={emotionId} onChange={(e) => setEmotionId(e.target.value)}>
            <option value="">—</option>
            {emotions.map((emo) => (
              <option key={emo.id} value={emo.id}>
                {emo.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Mục đích thương mại</span>
          <input
            value={commercialIntent}
            onChange={(e) => setCommercialIntent(e.target.value)}
            placeholder="VD: affiliate mỹ phẩm, không có, ..."
          />
        </label>
        <label>
          <span>Điểm (score)</span>
          <input type="number" step="0.1" value={score} onChange={(e) => setScore(e.target.value)} placeholder="—" />
        </label>
      </div>

      {error && <div className="idea-card-error">{error}</div>}

      {dirty && (
        <div className="idea-card-actions">
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 size={14} className="spin" /> : null}
            Lưu
          </button>
        </div>
      )}
    </div>
  );
}
