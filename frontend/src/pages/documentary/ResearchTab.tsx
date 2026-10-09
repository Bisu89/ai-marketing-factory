import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  addClaim,
  addSource,
  deleteClaim,
  deleteSource,
  getGateReview,
  listClaims,
  listSources,
  updateClaim,
  updateSource,
} from "../../api/documentary";
import type { Claim, ClaimInput, ClaimStatus, Source, SourceInput } from "../../api/documentary";
import { ActionFeedback, Badge, Field, Loading, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const EMPTY_SOURCE: SourceInput = {
  title: "", url: null, publisher: null, author: null, published_date: null, accessed_date: null, excerpt: null, notes: null,
};

const STATUS_VI: Record<ClaimStatus, { label: string; tone: "ok" | "warn" | "muted" }> = {
  verified: { label: "Đã xác minh", tone: "ok" },
  disputed: { label: "Còn tranh cãi", tone: "warn" },
  unverified: { label: "Chưa xác minh", tone: "muted" },
};

const orNull = (v: string) => (v.trim() === "" ? null : v);

function SourceForm({ initial, onSave, onCancel, busy }: {
  initial: SourceInput;
  onSave: (s: SourceInput) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [s, setS] = useState<SourceInput>(initial);
  const set = <K extends keyof SourceInput>(k: K, v: SourceInput[K]) => setS((p) => ({ ...p, [k]: v }));
  return (
    <form
      className="doc-item"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(s);
      }}
    >
      <div className="doc-row">
        <Field label="Tiêu đề nguồn *">
          <input value={s.title} onChange={(e) => set("title", e.target.value)} required />
        </Field>
        <Field label="URL (http/https)">
          <input value={s.url ?? ""} onChange={(e) => set("url", orNull(e.target.value))} placeholder="https://…" />
        </Field>
      </div>
      <div className="doc-row">
        <Field label="Nhà xuất bản">
          <input value={s.publisher ?? ""} onChange={(e) => set("publisher", orNull(e.target.value))} />
        </Field>
        <Field label="Tác giả">
          <input value={s.author ?? ""} onChange={(e) => set("author", orNull(e.target.value))} />
        </Field>
        <Field label="Ngày xuất bản">
          <input type="date" value={s.published_date ?? ""} onChange={(e) => set("published_date", orNull(e.target.value))} />
        </Field>
        <Field label="Ngày truy cập">
          <input type="date" value={s.accessed_date ?? ""} onChange={(e) => set("accessed_date", orNull(e.target.value))} />
        </Field>
      </div>
      <Field label="Trích đoạn liên quan" hint="Chép đúng từ nguồn; không tự viết lại.">
        <textarea rows={2} value={s.excerpt ?? ""} onChange={(e) => set("excerpt", orNull(e.target.value))} />
      </Field>
      <Field label="Ghi chú">
        <textarea rows={2} value={s.notes ?? ""} onChange={(e) => set("notes", orNull(e.target.value))} />
      </Field>
      <div className="doc-actions">
        <button className="btn btn-primary doc-btn-sm" type="submit" disabled={busy || !s.title.trim()}>
          Lưu nguồn
        </button>
        <button className="btn doc-btn-sm" type="button" onClick={onCancel}>
          Hủy
        </button>
      </div>
    </form>
  );
}

function ClaimForm({ initial, sources, onSave, onCancel, busy }: {
  initial: ClaimInput;
  sources: Source[];
  onSave: (c: ClaimInput) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [c, setC] = useState<ClaimInput>(initial);
  const toggle = (id: number) =>
    setC((p) => ({ ...p, source_ids: p.source_ids.includes(id) ? p.source_ids.filter((x) => x !== id) : [...p.source_ids, id] }));
  const needsSource = c.status !== "unverified" && c.source_ids.length === 0;
  return (
    <form
      className="doc-item"
      onSubmit={(e) => {
        e.preventDefault();
        onSave(c);
      }}
    >
      <Field label="Khẳng định lịch sử *">
        <textarea rows={2} value={c.text} onChange={(e) => setC({ ...c, text: e.target.value })} required />
      </Field>
      <div className="doc-row">
        <Field label="Trạng thái" hint="“Đã xác minh” và “Còn tranh cãi” cần ít nhất một nguồn.">
          <select value={c.status} onChange={(e) => setC({ ...c, status: e.target.value as ClaimStatus })}>
            {(Object.keys(STATUS_VI) as ClaimStatus[]).map((k) => (
              <option key={k} value={k}>
                {STATUS_VI[k].label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={c.status === "disputed" ? "Các cách giải thích khác nhau *" : "Ghi chú độ chắc chắn"}>
          <textarea rows={2} value={c.uncertainty_note ?? ""} onChange={(e) => setC({ ...c, uncertainty_note: orNull(e.target.value) })} />
        </Field>
      </div>
      <div>
        <div className="doc-muted">Nguồn hỗ trợ:</div>
        {sources.length === 0 && <div className="doc-muted">Chưa có nguồn nào — thêm nguồn ở phần trên trước.</div>}
        <div className="doc-row" style={{ gap: 14 }}>
          {sources.map((s) => (
            <label key={s.id} className="doc-check">
              <input type="checkbox" checked={c.source_ids.includes(s.id)} onChange={() => toggle(s.id)} /> {s.title}
            </label>
          ))}
        </div>
      </div>
      {needsSource && <div className="doc-issue-warn">Trạng thái này cần chọn ít nhất một nguồn.</div>}
      <div className="doc-actions">
        <button className="btn btn-primary doc-btn-sm" type="submit" disabled={busy || !c.text.trim() || needsSource}>
          Lưu khẳng định
        </button>
        <button className="btn doc-btn-sm" type="button" onClick={onCancel}>
          Hủy
        </button>
      </div>
    </form>
  );
}

export function ResearchTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const sources = useLoader(() => listSources(id), id);
  const claims = useLoader(() => listClaims(id), id);
  const review = useLoader(() => getGateReview(id, "research"), `${id}:${project.updated_at}`);
  const { busy, error, info, run } = useAction();
  const [editSource, setEditSource] = useState<number | "new" | null>(null);
  const [editClaim, setEditClaim] = useState<number | "new" | null>(null);

  async function afterChange() {
    await Promise.all([sources.reload(), claims.reload()]);
    reloadProject();
    void review.reload();
  }

  if (sources.loading || claims.loading) return <Loading />;
  const srcList = sources.data ?? [];
  const claimList = claims.data ?? [];
  const srcTitle = (sid: number) => srcList.find((s) => s.id === sid)?.title ?? `#${sid}`;

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? sources.error ?? claims.error} info={info} />
      <p className="doc-muted">
        Nguồn và khẳng định do bạn nhập thủ công — hệ thống không tự tìm hay bịa nguồn. Sửa phần này sau khi đã duyệt sẽ thu hồi
        các cổng duyệt phía sau.
      </p>

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Nguồn ({srcList.length})</h3>
          <button className="btn doc-btn-sm" onClick={() => setEditSource("new")} disabled={editSource === "new"}>
            <Plus size={14} /> Thêm nguồn
          </button>
        </div>
        {editSource === "new" && (
          <SourceForm
            initial={EMPTY_SOURCE}
            busy={busy !== null}
            onCancel={() => setEditSource(null)}
            onSave={async (s) => (await run("src", () => addSource(id, s))) && (setEditSource(null), void afterChange())}
          />
        )}
        <div className="doc-list">
          {srcList.map((s) =>
            editSource === s.id ? (
              <SourceForm
                key={s.id}
                initial={s}
                busy={busy !== null}
                onCancel={() => setEditSource(null)}
                onSave={async (b) => (await run("src", () => updateSource(id, s.id, b))) && (setEditSource(null), void afterChange())}
              />
            ) : (
              <div key={s.id} className="doc-item">
                <div className="doc-item-head">
                  <strong className="grow">{s.title}</strong>
                  <button className="btn doc-btn-sm" onClick={() => setEditSource(s.id)}>
                    <Pencil size={13} /> Sửa
                  </button>
                  <button
                    className="btn doc-btn-sm doc-btn-danger"
                    disabled={busy !== null}
                    onClick={async () => {
                      if (!window.confirm(`Xóa nguồn “${s.title}”?`)) return;
                      (await run("del", () => deleteSource(id, s.id))) !== undefined && void afterChange();
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                <div className="doc-muted">
                  {[s.publisher, s.author, s.published_date].filter(Boolean).join(" · ")}
                  {s.url && (
                    <>
                      {" · "}
                      <a href={s.url} target="_blank" rel="noreferrer noopener">
                        {s.url}
                      </a>
                    </>
                  )}
                </div>
                {s.excerpt && <div className="doc-narration">“{s.excerpt}”</div>}
              </div>
            ),
          )}
          {srcList.length === 0 && editSource !== "new" && <p className="doc-muted">Chưa có nguồn nào.</p>}
        </div>
      </div>

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Khẳng định ({claimList.length})</h3>
          <button className="btn doc-btn-sm" onClick={() => setEditClaim("new")} disabled={editClaim === "new"}>
            <Plus size={14} /> Thêm khẳng định
          </button>
        </div>
        {editClaim === "new" && (
          <ClaimForm
            initial={{ text: "", status: "unverified", uncertainty_note: null, source_ids: [] }}
            sources={srcList}
            busy={busy !== null}
            onCancel={() => setEditClaim(null)}
            onSave={async (c) => (await run("claim", () => addClaim(id, c))) && (setEditClaim(null), void afterChange())}
          />
        )}
        <div className="doc-list">
          {claimList.map((c: Claim) =>
            editClaim === c.id ? (
              <ClaimForm
                key={c.id}
                initial={c}
                sources={srcList}
                busy={busy !== null}
                onCancel={() => setEditClaim(null)}
                onSave={async (b) => (await run("claim", () => updateClaim(id, c.id, b))) && (setEditClaim(null), void afterChange())}
              />
            ) : (
              <div key={c.id} className="doc-item">
                <div className="doc-item-head">
                  <Badge tone={STATUS_VI[c.status].tone}>{STATUS_VI[c.status].label}</Badge>
                  <span className="doc-muted">#{c.id}</span>
                  <span className="grow" />
                  <button className="btn doc-btn-sm" onClick={() => setEditClaim(c.id)}>
                    <Pencil size={13} /> Sửa
                  </button>
                  <button
                    className="btn doc-btn-sm doc-btn-danger"
                    disabled={busy !== null}
                    onClick={async () => {
                      if (!window.confirm("Xóa khẳng định này?")) return;
                      (await run("del", () => deleteClaim(id, c.id))) !== undefined && void afterChange();
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
                <div className="doc-narration">{c.text}</div>
                {c.uncertainty_note && <div className="doc-muted">Ghi chú: {c.uncertainty_note}</div>}
                <div className="doc-muted">Nguồn: {c.source_ids.length ? c.source_ids.map(srcTitle).join("; ") : "— chưa có —"}</div>
              </div>
            ),
          )}
          {claimList.length === 0 && editClaim !== "new" && <p className="doc-muted">Chưa có khẳng định nào.</p>}
        </div>
      </div>

      <ReviewBox review={review.data} title="Kiểm tra cổng 1" />
    </div>
  );
}
