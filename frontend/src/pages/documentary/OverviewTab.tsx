import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, RotateCcw, XCircle } from "lucide-react";
import {
  advanceProject,
  approveGate,
  getApprovals,
  getGateReview,
  GATE_LABELS,
  rejectGate,
  resumeProject,
  rewindProject,
  STATE_LABELS,
} from "../../api/documentary";
import type { GateStatusName } from "../../api/documentary";
import { ActionFeedback, Badge, Field, Notice, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const ORDER = [
  "draft",
  "research_review",
  "script_review",
  "storyboard_review",
  "asset_generation",
  "asset_review",
  "audio_ready",
  "render_preview",
  "final_review",
  "approved",
  "exported",
];

const GATE_STATUS_VI: Record<GateStatusName, { label: string; tone: "ok" | "warn" | "bad" | "muted" }> = {
  approved: { label: "Đã duyệt", tone: "ok" },
  pending: { label: "Chưa duyệt", tone: "muted" },
  stale: { label: "Cũ — cần duyệt lại", tone: "warn" },
  rejected: { label: "Bị từ chối", tone: "bad" },
};

export function OverviewTab({ project, reloadProject }: TabProps) {
  const { busy, error, info, run } = useAction();
  const [note, setNote] = useState("");
  const [rewindTo, setRewindTo] = useState("");
  const currentGate = project.gates.find((g) => g.review_state === project.state);
  const approvals = useLoader(() => getApprovals(project.id), `${project.id}:${project.updated_at}`);
  const review = useLoader(
    () => (currentGate ? getGateReview(project.id, currentGate.gate) : Promise.resolve(null)),
    `${project.id}:${project.updated_at}:${currentGate?.gate ?? ""}`,
  );

  useEffect(() => setNote(""), [project.state]);

  const rewindable = ORDER.slice(1, Math.max(ORDER.indexOf(project.state), 0));
  const afterAction = () => {
    reloadProject();
    void approvals.reload();
    void review.reload();
  };

  return (
    <div className="doc-page">
      <ActionFeedback error={error} info={info} />

      {project.state === "failed" && (
        <Notice kind="error">
          Dự án đang ở trạng thái lỗi (từ bước “{STATE_LABELS[project.failed_from_state ?? ""] ?? project.failed_from_state}”):{" "}
          {project.error_message}
          <div style={{ marginTop: 8 }}>
            <button className="btn doc-btn-sm" disabled={busy !== null} onClick={async () => (await run("resume", () => resumeProject(project.id))) && afterAction()}>
              Tiếp tục từ bước đó
            </button>
          </div>
        </Notice>
      )}

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Bước hiện tại: {STATE_LABELS[project.state] ?? project.state}</h3>
          {project.next_state && (
            <button
              className="btn btn-primary"
              disabled={busy !== null || project.blockers.length > 0}
              onClick={async () => (await run("advance", () => advanceProject(project.id))) && afterAction()}
            >
              Sang bước “{STATE_LABELS[project.next_state] ?? project.next_state}” <ArrowRight size={15} />
            </button>
          )}
        </div>
        {project.blockers.length > 0 && (
          <Notice kind="warn">
            Chưa thể sang bước tiếp: cần duyệt {project.blockers.map((b) => GATE_LABELS[b] ?? b).join(", ")}.
          </Notice>
        )}
        {!project.next_state && project.state !== "failed" && <p className="doc-muted">Dự án đã ở bước cuối.</p>}
        <p className="doc-muted">
          Render preview/bản cuối ở tab “Render”. Xuất file (export) chưa có trong phiên bản này.
        </p>
      </div>

      {currentGate && (
        <div className="doc-card">
          <h3>{GATE_LABELS[currentGate.gate]}</h3>
          <div className="doc-row">
            <Badge tone={GATE_STATUS_VI[currentGate.status].tone}>{GATE_STATUS_VI[currentGate.status].label}</Badge>
            <span className="doc-muted">phiên bản nội dung hiện tại: v{currentGate.current_version}</span>
          </div>
          <ReviewBox review={review.data} title="Kiểm tra trước khi duyệt" />
          <Field label="Ghi chú (tùy chọn)">
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="doc-actions">
            <button
              className="btn btn-primary"
              disabled={busy !== null || currentGate.status === "approved"}
              onClick={async () => (await run("approve", () => approveGate(project.id, currentGate.gate, note), () => "Đã duyệt cổng này.")) && afterAction()}
            >
              <CheckCircle2 size={15} /> Duyệt
            </button>
            <button
              className="btn doc-btn-danger"
              disabled={busy !== null}
              onClick={async () => {
                if (!window.confirm("Từ chối cổng này? Bạn cần sửa nội dung rồi duyệt lại.")) return;
                (await run("reject", () => rejectGate(project.id, currentGate.gate, note))) && afterAction();
              }}
            >
              <XCircle size={15} /> Từ chối
            </button>
          </div>
        </div>
      )}

      <div className="doc-card">
        <h3>Tất cả cổng duyệt</h3>
        <div className="doc-table-wrap">
          <table className="doc-table">
            <tbody>
              {project.gates.map((g) => (
                <tr key={g.gate}>
                  <td>{GATE_LABELS[g.gate]}</td>
                  <td>
                    <Badge tone={GATE_STATUS_VI[g.status].tone}>{GATE_STATUS_VI[g.status].label}</Badge>
                  </td>
                  <td className="doc-muted">
                    {g.approved_version !== null ? `đã duyệt v${g.approved_version} · ` : ""}hiện v{g.current_version}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="doc-muted">
          Sửa nội dung đã duyệt (nguồn, kịch bản, ảnh, audio…) sẽ làm cổng đó và các cổng sau nó mất hiệu lực, dự án quay về bước duyệt tương ứng.
        </p>
      </div>

      {rewindable.length > 0 && (
        <div className="doc-card">
          <h3>Quay lại bước trước</h3>
          <div className="doc-row">
            <Field label="Quay về">
              <select value={rewindTo} onChange={(e) => setRewindTo(e.target.value)}>
                <option value="">— chọn bước —</option>
                {rewindable.map((s) => (
                  <option key={s} value={s}>
                    {STATE_LABELS[s]}
                  </option>
                ))}
              </select>
            </Field>
            <button
              className="btn"
              disabled={busy !== null || !rewindTo}
              onClick={async () => {
                if (!window.confirm(`Quay về “${STATE_LABELS[rewindTo]}”? Mọi cổng duyệt từ bước đó trở đi sẽ bị thu hồi.`)) return;
                (await run("rewind", () => rewindProject(project.id, rewindTo, note))) && (setRewindTo(""), afterAction());
              }}
            >
              <RotateCcw size={15} /> Quay lại
            </button>
          </div>
        </div>
      )}

      <div className="doc-card">
        <h3>Lịch sử duyệt</h3>
        {approvals.data && approvals.data.length === 0 && <p className="doc-muted">Chưa có.</p>}
        <div className="doc-list">
          {approvals.data
            ?.slice()
            .reverse()
            .map((a) => (
              <div key={a.id} className="doc-item-head">
                <Badge tone={a.decision === "approved" ? "ok" : a.decision === "rejected" ? "bad" : "warn"}>
                  {a.decision === "approved" ? "Duyệt" : a.decision === "rejected" ? "Từ chối" : "Thu hồi"}
                </Badge>
                <span>{GATE_LABELS[a.gate] ?? a.gate}</span>
                <span className="doc-muted">v{a.artifact_version} · {new Date(a.created_at).toLocaleString("vi-VN")}</span>
                {a.note && <span className="doc-muted">— {a.note}</span>}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
