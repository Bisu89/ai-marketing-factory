import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, LayoutList, Plus, Trash2 } from "lucide-react";
import { listScenes, planStoryboard, PRESETS, SECTION_LABELS, updateScene } from "../../api/documentary";
import type { AssetState, OnScreenText, Scene } from "../../api/documentary";
import { ActionFeedback, Badge, Busy, Field, Loading, Notice, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

export const ASSET_STATE_VI: Record<AssetState, { label: string; tone: "ok" | "warn" | "bad" | "muted" | "info" }> = {
  programmatic: { label: "Đồ họa lập trình", tone: "info" },
  missing: { label: "Chưa có ảnh", tone: "bad" },
  pending: { label: "Ảnh chờ duyệt", tone: "warn" },
  approved: { label: "Ảnh đã duyệt", tone: "ok" },
  rejected: { label: "Ảnh bị từ chối", tone: "bad" },
  stale: { label: "Ảnh cũ (mô tả đã đổi)", tone: "warn" },
  file_missing: { label: "Mất file ảnh", tone: "bad" },
};

const PRESET_HINT: Record<string, string> = {
  NewspaperStack: "Chồng báo/tư liệu cắt dán",
  ArchivalPortrait: "Chân dung tư liệu",
  MapZoom: "Bản đồ phóng to (đồ họa)",
  TimelineBuild: "Dòng thời gian dựng dần (đồ họa)",
  BigNumber: "Con số lớn (đồ họa)",
  EvidenceBoard: "Bảng bằng chứng (đồ họa)",
  PhotoKenBurns: "Ảnh chuyển động nhẹ",
  HeadlineImpact: "Tiêu đề nhấn mạnh (đồ họa)",
  SplitComparison: "So sánh chia đôi",
};

function SceneEditor({ scene, onSaved, projectId }: { scene: Scene; onSaved: () => void; projectId: number }) {
  const { busy, error, run } = useAction();
  const [preset, setPreset] = useState(scene.visual_preset);
  const [objective, setObjective] = useState(scene.visual_objective);
  const [texts, setTexts] = useState<OnScreenText[]>(scene.on_screen_text);
  const [motion, setMotion] = useState(scene.motion_notes ?? "");
  const [sfx, setSfx] = useState(scene.sfx_cues.join(", "));

  async function save() {
    const r = await run("save", () =>
      updateScene(projectId, scene.id, {
        visual_preset: preset,
        visual_objective: objective,
        on_screen_text: texts.filter((t) => t.text.trim()),
        motion_notes: motion,
        sfx_cues: sfx.split(",").map((x) => x.trim()).filter(Boolean),
      }),
    );
    if (r) onSaved();
  }

  return (
    <div className="doc-item" style={{ background: "var(--surface-alt)" }}>
      {error && <Notice kind="error">{error}</Notice>}
      <div className="doc-row">
        <Field label="Preset hình ảnh" hint="Đổi sang preset đồ họa sẽ bỏ ảnh đã gán; đổi sang preset ảnh sẽ cần ảnh mới.">
          <select value={preset} onChange={(e) => setPreset(e.target.value)}>
            {PRESETS.map((p) => (
              <option key={p} value={p}>
                {p} — {PRESET_HINT[p]}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Mô tả hình ảnh / prompt" hint="Với cảnh dùng ảnh: đây là prompt xuất ra CSV. Đổi mô tả sẽ đánh dấu ảnh cũ là lỗi thời.">
        <textarea rows={3} value={objective} onChange={(e) => setObjective(e.target.value)} />
      </Field>
      <div>
        <div className="doc-muted">Chữ trên màn hình (dựng bằng code, không nhúng vào ảnh AI):</div>
        {texts.map((t, i) => (
          <div key={i} className="doc-row" style={{ marginTop: 6 }}>
            <input
              className="doc-input"
              style={{ flex: 3 }}
              value={t.text}
              maxLength={300}
              onChange={(e) => setTexts((p) => p.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))}
            />
            <select
              className="doc-input"
              value={t.role}
              onChange={(e) => setTexts((p) => p.map((x, k) => (k === i ? { ...x, role: e.target.value as OnScreenText["role"] } : x)))}
            >
              <option value="headline">tiêu đề</option>
              <option value="label">nhãn</option>
              <option value="date">ngày/năm</option>
              <option value="number">con số</option>
              <option value="caption">chú thích</option>
            </select>
            <button className="btn doc-btn-sm doc-btn-danger" onClick={() => setTexts((p) => p.filter((_, k) => k !== i))} aria-label="Xóa dòng chữ">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        <button className="btn doc-btn-sm" style={{ marginTop: 6 }} onClick={() => setTexts((p) => [...p, { text: "", role: "caption" }])}>
          <Plus size={13} /> Thêm dòng chữ
        </button>
      </div>
      <div className="doc-row">
        <Field label="Ghi chú chuyển động">
          <input value={motion} onChange={(e) => setMotion(e.target.value)} />
        </Field>
        <Field label="Gợi ý hiệu ứng âm thanh (cách nhau bằng dấu phẩy)">
          <input value={sfx} onChange={(e) => setSfx(e.target.value)} />
        </Field>
      </div>
      <div className="doc-actions">
        <button className="btn btn-primary doc-btn-sm" disabled={busy !== null} onClick={() => void save()}>
          Lưu cảnh {scene.scene_key}
        </button>
        {busy && <Busy />}
      </div>
    </div>
  );
}

export function StoryboardTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const scenes = useLoader(() => listScenes(id), `${id}:${project.updated_at}`);
  const { busy, error, info, run } = useAction();
  const [open, setOpen] = useState<number | null>(null);
  const scriptApproved = project.gates.find((g) => g.gate === "script")?.status === "approved";

  async function plan() {
    const r = await run(
      "plan",
      () => planStoryboard(id),
      (x) => `${x.scenes} cảnh (${x.created} mới, ${x.kept} giữ nguyên, ${x.removed} bỏ) · ${x.image_groups} nhóm ảnh · ${x.programmatic} cảnh đồ họa lập trình.`,
    );
    if (r) {
      await scenes.reload();
      reloadProject();
    }
  }

  const list = scenes.data ?? [];
  const totalExp = list.reduce((a, s) => a + s.expected_duration, 0);

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? scenes.error} info={info} />
      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Storyboard từ kịch bản đã duyệt</h3>
          <div className="doc-actions">
            <button className="btn btn-primary" disabled={busy !== null || !scriptApproved} onClick={() => void plan()}>
              <LayoutList size={15} /> {list.length ? "Lập lại storyboard" : "Lập storyboard"}
            </button>
            {busy && <Busy />}
          </div>
        </div>
        {!scriptApproved && <Notice kind="warn">Cần duyệt kịch bản (cổng 2) trước khi lập storyboard.</Notice>}
        <p className="doc-muted">
          Cảnh được cắt theo câu và đoạn, không theo số giây cố định. Lập lại storyboard chỉ tạo cảnh mới cho phần lời dẫn đã đổi —
          các cảnh giữ nguyên vẫn giữ mã, ảnh và chỉnh sửa của bạn.
          {list.length > 0 && ` Hiện có ${list.length} cảnh, ước tính ${Math.round(totalExp / 60 * 10) / 10} phút (ước tính; thời lượng thật có sau khi có audio).`}
        </p>
      </div>

      {scenes.loading && <Loading />}
      {!scenes.loading && list.length === 0 && <p className="doc-muted">Chưa có cảnh nào.</p>}
      {list.length > 0 && (
        <div className="doc-card doc-table-wrap">
          <table className="doc-table">
            <thead>
              <tr>
                <th />
                <th>Cảnh</th>
                <th>Lời dẫn</th>
                <th>Preset</th>
                <th>Thời lượng</th>
                <th>Hình ảnh</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <Fragment key={s.id}>
                  <tr>
                    <td>
                      <button className="btn doc-btn-sm" onClick={() => setOpen(open === s.id ? null : s.id)} aria-label={`Mở/đóng cảnh ${s.scene_key}`}>
                        {open === s.id ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                      </button>
                    </td>
                    <td>
                      <strong>{s.scene_key}</strong>
                      <div className="doc-muted">{SECTION_LABELS[s.section_kind]}</div>
                      {s.user_edited && <Badge tone="info">đã sửa tay</Badge>}
                    </td>
                    <td style={{ maxWidth: 420 }}>{s.narration_text}</td>
                    <td>{s.visual_preset}</td>
                    <td className="doc-mono">
                      {s.actual_duration !== null ? (
                        <>
                          {s.actual_duration.toFixed(1)}s <span className="doc-muted">(đo từ audio)</span>
                        </>
                      ) : (
                        <>
                          ~{s.expected_duration.toFixed(1)}s <span className="doc-muted">(ước tính)</span>
                        </>
                      )}
                    </td>
                    <td>
                      <Badge tone={ASSET_STATE_VI[s.asset_state].tone}>{ASSET_STATE_VI[s.asset_state].label}</Badge>
                      {s.image_group && s.image_group !== s.scene_key && <div className="doc-muted">dùng chung ảnh {s.image_group}</div>}
                    </td>
                  </tr>
                  {open === s.id && (
                    <tr>
                      <td />
                      <td colSpan={5}>
                        <SceneEditor
                          scene={s}
                          projectId={id}
                          onSaved={() => {
                            void scenes.reload();
                            reloadProject();
                          }}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
