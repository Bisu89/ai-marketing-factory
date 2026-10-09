import { useEffect, useState } from "react";
import { Plus, Save, Sparkles, Trash2 } from "lucide-react";
import {
  generateOutline,
  generateScript,
  getGateReview,
  getScript,
  getScriptHistory,
  getScriptProviders,
  listClaims,
  saveScript,
  SECTION_LABELS,
} from "../../api/documentary";
import type { Claim, OutlineItem, Script, ScriptSection, SectionKind } from "../../api/documentary";
import { ActionFeedback, Badge, Busy, Loading, Notice, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const KINDS = Object.keys(SECTION_LABELS) as SectionKind[];

function fmtMin(sec: number) {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

function ClaimPicker({ claims, value, onChange }: { claims: Claim[]; value: number[]; onChange: (v: number[]) => void }) {
  const toggle = (id: number) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id].sort((a, b) => a - b));
  return (
    <details>
      <summary className="doc-muted" style={{ cursor: "pointer" }}>
        Khẳng định/nguồn: {value.length ? value.map((v) => `#${v}`).join(", ") : "— chưa gắn —"}
      </summary>
      <div className="doc-list" style={{ marginTop: 6 }}>
        {claims.length === 0 && <span className="doc-muted">Chưa có khẳng định (thêm ở tab Nghiên cứu).</span>}
        {claims.map((c) => (
          <label key={c.id} className="doc-check">
            <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)} />
            <Badge tone={c.status === "verified" ? "ok" : c.status === "disputed" ? "warn" : "muted"}>#{c.id}</Badge>
            {c.text.slice(0, 90)}
          </label>
        ))}
      </div>
    </details>
  );
}

export function ScriptTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const script = useLoader(() => getScript(id), id);
  const history = useLoader(() => getScriptHistory(id), `${id}:${script.data?.version ?? 0}`);
  const claims = useLoader(() => listClaims(id), id);
  const providers = useLoader(getScriptProviders, "providers");
  const review = useLoader(() => getGateReview(id, "script"), `${id}:${script.data?.version ?? 0}:${project.updated_at}`);
  const { busy, error, info, run } = useAction();

  const [provider, setProvider] = useState<"mock" | "llm">("mock");
  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [sections, setSections] = useState<ScriptSection[]>([]);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (script.data) {
      setOutline(script.data.outline);
      setSections(script.data.sections);
      setDirty(false);
    } else {
      setOutline([]);
      setSections([]);
    }
  }, [script.data]);

  const edit = <T,>(setter: (fn: (p: T) => T) => void, fn: (p: T) => T) => {
    setter(fn);
    setDirty(true);
  };

  function confirmReplace(): boolean {
    if (dirty && !window.confirm("Bạn có chỉnh sửa chưa lưu. Tiếp tục sẽ thay thế bản đang sửa. Tiếp tục?")) return false;
    if (provider === "llm" && !window.confirm("Provider “llm” sẽ gọi API AI thật (tốn token/chi phí). Tiếp tục?")) return false;
    return true;
  }

  async function afterSave(s: Script | undefined) {
    if (!s) return;
    await script.reload();
    reloadProject();
  }

  if (script.loading || claims.loading) return <Loading />;
  const claimList = claims.data ?? [];
  const cur = script.data;
  const hasLlm = providers.data?.script.includes("llm");

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? script.error ?? claims.error} info={info} />

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Tạo từ khẳng định đã nhập</h3>
          <div className="doc-actions">
            <select className="doc-input" value={provider} onChange={(e) => setProvider(e.target.value as "mock" | "llm")} aria-label="Provider">
              <option value="mock">mock — mẫu offline, miễn phí</option>
              {hasLlm && <option value="llm">llm — dùng API AI (tốn token)</option>}
            </select>
            <button
              className="btn doc-btn-sm"
              disabled={busy !== null}
              onClick={async () => confirmReplace() && afterSave(await run("outline", () => generateOutline(id, provider), () => "Đã tạo dàn ý (phiên bản mới)."))}
            >
              <Sparkles size={14} /> 1. Tạo dàn ý
            </button>
            <button
              className="btn doc-btn-sm"
              disabled={busy !== null || !cur || cur.outline.length === 0}
              onClick={async () => confirmReplace() && afterSave(await run("script", () => generateScript(id, provider), () => "Đã tạo kịch bản đầy đủ (phiên bản mới)."))}
            >
              <Sparkles size={14} /> 2. Tạo kịch bản
            </button>
            {busy && <Busy />}
          </div>
        </div>
        <p className="doc-muted">
          AI chỉ được sắp xếp và diễn đạt lại các khẳng định bạn đã nhập, không thêm sự kiện. Mỗi đoạn nêu sự kiện phải gắn khẳng định có nguồn.
        </p>
      </div>

      {!cur && <Notice kind="info">Chưa có kịch bản. Tạo dàn ý ở trên, hoặc tự viết bằng cách tạo khung trống.</Notice>}

      {cur === null || sections.length === 0 ? (
        <div className="doc-card">
          <button
            className="btn doc-btn-sm"
            style={{ alignSelf: "flex-start" }}
            onClick={() =>
              edit(setSections, () =>
                KINDS.map((k) => ({ kind: k, heading: SECTION_LABELS[k], paragraphs: [{ text: "", factual: true, claim_ids: [] }] })),
              )
            }
          >
            <Plus size={14} /> Tạo khung 7 phần trống để tự viết
          </button>
        </div>
      ) : null}

      {cur && (
        <div className="doc-card">
          <div className="doc-card-head">
            <h3>
              Phiên bản v{cur.version} <Badge tone="muted">{cur.origin}</Badge>
            </h3>
            <span className="doc-muted">
              {cur.word_count} từ · ước tính {fmtMin(cur.estimated_seconds)} (mục tiêu {fmtMin(cur.target_seconds[0])}–{fmtMin(cur.target_seconds[1])}){" "}
              {cur.sections.length > 0 && (cur.within_target ? <Badge tone="ok">trong mục tiêu</Badge> : <Badge tone="warn">ngoài mục tiêu</Badge>)}
            </span>
          </div>
          <p className="doc-muted">Độ dài chỉ là ước tính; độ dài thật đo từ audio ở tab “Giọng đọc & Timeline”.</p>
          {history.data && history.data.length > 1 && (
            <div className="doc-actions">
              <span className="doc-muted">Khôi phục phiên bản cũ:</span>
              <select
                className="doc-input"
                value=""
                onChange={(e) => {
                  const v = history.data?.find((h) => h.version === Number(e.target.value));
                  if (v && (!dirty || window.confirm("Thay bản đang sửa bằng phiên bản này (chưa lưu)?"))) {
                    setOutline(v.outline);
                    setSections(v.sections);
                    setDirty(true);
                  }
                }}
              >
                <option value="">— chọn —</option>
                {history.data.map((h) => (
                  <option key={h.version} value={h.version}>
                    v{h.version} · {h.origin} · {h.word_count} từ
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {outline.length > 0 && (
        <div className="doc-card">
          <h3>Dàn ý</h3>
          <div className="doc-list">
            {outline.map((o, i) => (
              <div key={o.kind} className="doc-item">
                <strong>{SECTION_LABELS[o.kind]}</strong>
                <textarea
                  className="doc-input"
                  rows={2}
                  value={o.summary}
                  onChange={(e) => edit(setOutline, (p) => p.map((x, k) => (k === i ? { ...x, summary: e.target.value } : x)))}
                />
                <ClaimPicker claims={claimList} value={o.claim_ids} onChange={(v) => edit(setOutline, (p) => p.map((x, k) => (k === i ? { ...x, claim_ids: v } : x)))} />
              </div>
            ))}
          </div>
        </div>
      )}

      {sections.length > 0 && (
        <div className="doc-card">
          <h3>Kịch bản</h3>
          <div className="doc-list">
            {sections.map((s, si) => (
              <div key={s.kind} className="doc-item">
                <div className="doc-item-head">
                  <strong className="grow">{SECTION_LABELS[s.kind]}</strong>
                </div>
                {s.paragraphs.map((p, pi) => (
                  <div key={pi} className="doc-item" style={{ background: "var(--surface-alt)" }}>
                    <textarea
                      className="doc-input"
                      rows={4}
                      value={p.text}
                      placeholder="Lời dẫn…"
                      onChange={(e) =>
                        edit(setSections, (prev) =>
                          prev.map((x, a) => (a === si ? { ...x, paragraphs: x.paragraphs.map((y, b) => (b === pi ? { ...y, text: e.target.value } : y)) } : x)),
                        )
                      }
                    />
                    <div className="doc-actions">
                      <label className="doc-check">
                        <input
                          type="checkbox"
                          checked={p.factual}
                          onChange={(e) =>
                            edit(setSections, (prev) =>
                              prev.map((x, a) => (a === si ? { ...x, paragraphs: x.paragraphs.map((y, b) => (b === pi ? { ...y, factual: e.target.checked } : y)) } : x)),
                            )
                          }
                        />
                        Nêu sự kiện lịch sử (cần nguồn)
                      </label>
                      <button
                        className="btn doc-btn-sm doc-btn-danger"
                        onClick={() =>
                          edit(setSections, (prev) => prev.map((x, a) => (a === si ? { ...x, paragraphs: x.paragraphs.filter((_, b) => b !== pi) } : x)))
                        }
                      >
                        <Trash2 size={13} /> Xóa đoạn
                      </button>
                    </div>
                    <ClaimPicker
                      claims={claimList}
                      value={p.claim_ids}
                      onChange={(v) =>
                        edit(setSections, (prev) =>
                          prev.map((x, a) => (a === si ? { ...x, paragraphs: x.paragraphs.map((y, b) => (b === pi ? { ...y, claim_ids: v } : y)) } : x)),
                        )
                      }
                    />
                  </div>
                ))}
                <button
                  className="btn doc-btn-sm"
                  style={{ alignSelf: "flex-start" }}
                  onClick={() =>
                    edit(setSections, (prev) =>
                      prev.map((x, a) => (a === si ? { ...x, paragraphs: [...x.paragraphs, { text: "", factual: true, claim_ids: [] }] } : x)),
                    )
                  }
                >
                  <Plus size={13} /> Thêm đoạn
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {(outline.length > 0 || sections.length > 0) && (
        <div className="doc-actions">
          <button
            className="btn btn-primary"
            disabled={busy !== null || !dirty}
            onClick={async () => {
              const cleaned = sections.map((s) => ({ ...s, paragraphs: s.paragraphs.filter((p) => p.text.trim() !== "") }));
              await afterSave(
                await run("save", () => saveScript(id, { outline, sections: cleaned }), (r) => `Đã lưu thành phiên bản v${r.version}. Các cổng duyệt phía sau (nếu có) đã bị thu hồi.`),
              );
            }}
          >
            <Save size={15} /> Lưu thành phiên bản mới
          </button>
          {dirty && <Badge tone="warn">Có thay đổi chưa lưu</Badge>}
        </div>
      )}

      {dirty && <Notice kind="warn">Kiểm tra bên dưới là của bản đã lưu, chưa gồm các chỉnh sửa hiện tại.</Notice>}
      <ReviewBox review={review.data} title="Kiểm tra cổng 2 (nguồn & độ phủ)" />
    </div>
  );
}
