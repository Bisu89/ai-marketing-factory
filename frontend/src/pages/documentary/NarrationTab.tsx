import { useEffect, useState } from "react";
import { AudioLines, Download, Layers, Mic, Timer } from "lucide-react";
import {
  alignTimeline,
  assembleTimeline,
  buildMaster,
  clearSceneStart,
  estimateNarration,
  fmtTime,
  generateNarration,
  getAlignmentStatus,
  getGateReview,
  getSubtitles,
  getTimeline,
  getTtsBackends,
  listSegments,
  masterAudioUrl,
  planNarration,
  segmentAudioUrl,
  setSceneStart,
  srtUrl,
} from "../../api/documentary";
import type { Estimate, SceneTiming } from "../../api/documentary";
import { ActionFeedback, Badge, Busy, Field, Loading, Notice, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const SOURCE_VI: Record<SceneTiming["source"], { label: string; tone: "ok" | "warn" | "info" | "muted" }> = {
  tts_provider: { label: "timestamp từ TTS", tone: "ok" },
  whisper_local: { label: "Whisper (máy bạn)", tone: "ok" },
  estimated: { label: "ƯỚC LƯỢNG — chưa chính xác", tone: "warn" },
  manual: { label: "chỉnh tay", tone: "info" },
};

const BACKEND_VI: Record<string, string> = {
  edge: "edge — Microsoft Edge (miễn phí, có timestamp từng từ)",
  edge_en: "edge_en — giọng tiếng Anh (miễn phí, có timestamp từng từ)",
  elevenlabs: "elevenlabs — trả phí",
  mock: "mock — im lặng, chỉ để thử luồng",
};

function money(v: number | null) {
  return v === null ? "chưa biết (chưa cấu hình giá)" : `$${v.toFixed(4)}`;
}

function SceneStartEditor({ projectId, t, onDone }: { projectId: number; t: SceneTiming; onDone: () => void }) {
  const { busy, error, run } = useAction();
  const [val, setVal] = useState(t.start.toFixed(2));
  useEffect(() => setVal(t.start.toFixed(2)), [t.start]);
  return (
    <div>
      <div className="doc-actions">
        <input className="doc-input" style={{ width: 84 }} value={val} onChange={(e) => setVal(e.target.value)} inputMode="decimal" aria-label={`Bắt đầu cảnh ${t.scene_key}`} />
        <button
          className="btn doc-btn-sm"
          disabled={busy !== null || !Number.isFinite(Number(val)) || Number(val) === Number(t.start.toFixed(2))}
          onClick={async () => (await run("set", () => setSceneStart(projectId, t.scene_key, Number(val)))) && onDone()}
        >
          Lưu
        </button>
        {t.source === "manual" && (
          <button className="btn doc-btn-sm" disabled={busy !== null} onClick={async () => (await run("clear", () => clearSceneStart(projectId, t.scene_key))) !== undefined && onDone()}>
            Bỏ chỉnh tay
          </button>
        )}
      </div>
      {error && <div className="doc-issue-bad" style={{ fontSize: 12 }}>{error}</div>}
    </div>
  );
}

export function NarrationTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const stamp = `${id}:${project.updated_at}`;
  const segs = useLoader(() => listSegments(id), stamp);
  const timeline = useLoader(() => getTimeline(id), stamp);
  const subs = useLoader(() => getSubtitles(id), stamp);
  const backends = useLoader(getTtsBackends, "backends");
  const align = useLoader(getAlignmentStatus, "align");
  const review = useLoader(() => getGateReview(id, "narration_timing"), stamp);
  const { busy, error, info, run, notify } = useAction();

  const [backend, setBackend] = useState("");
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [method, setMethod] = useState("auto");
  const [masterTick, setMasterTick] = useState(0);
  const [showSubs, setShowSubs] = useState(false);

  useEffect(() => {
    if (!backend && backends.data) setBackend(backends.data.backends.includes("edge") ? "edge" : backends.data.backends[0] ?? "");
  }, [backends.data, backend]);

  const gate3 = project.gates.find((g) => g.gate === "storyboard_assets")?.status === "approved";
  const refresh = () => {
    void segs.reload();
    void timeline.reload();
    void subs.reload();
    void review.reload();
    setMasterTick((n) => n + 1);
    reloadProject();
  };

  async function generate() {
    const est = await run("est", () => estimateNarration(id, backend));
    if (!est) return;
    setEstimate(est);
    const done = (res: { generated: string[]; skipped_cached: number; failed: unknown[] }) =>
      res.generated.length === 0 && res.failed.length === 0
        ? `Không có gì để tạo: ${res.skipped_cached} đoạn đã có audio khớp (dùng lại từ cache).`
        : `Đã tạo ${res.generated.length} đoạn, ${res.skipped_cached} đoạn dùng lại cache${res.failed.length ? `, ${res.failed.length} đoạn lỗi (xem bên dưới)` : ""}.`;

    let confirm = false;
    if (est.paid && est.segments_to_generate > 0) {
      const msg =
        `Backend TRẢ PHÍ “${est.backend}”: tạo ${est.segments_to_generate} đoạn, ${est.chars} ký tự.
` +
        `Chi phí ước tính: ${money(est.estimated_cost_usd)}. Đã chi: $${est.spent_usd.toFixed(4)}` +
        `${est.budget_usd !== null ? ` / ngân sách $${est.budget_usd}` : ""}.

Xác nhận chạy?`;
      if (!window.confirm(msg)) return;
      confirm = true;
    }
    // A free backend can still be refused by the server (e.g. over budget); then ask once more.
    const first = await run("gen", async () => {
      try {
        return { res: await generateNarration(id, backend, confirm) };
      } catch (e) {
        if (!confirm && e instanceof Error && /confirm=true/.test(e.message)) return { ask: e.message };
        throw e;
      }
    });
    if (!first) return;
    if ("res" in first) {
      notify(done(first.res));
      refresh();
    } else if (window.confirm(`${first.ask}

Vẫn chạy?`)) {
      const again = await run("gen", () => generateNarration(id, backend, true), done);
      if (again) refresh();
    }
  }

  if (segs.loading || timeline.loading) return <Loading />;
  const segments = segs.data ?? [];
  const timings = timeline.data ?? [];
  const allCurrent = segments.length > 0 && segments.every((s) => s.is_current);
  const failed = segments.filter((s) => s.status === "failed");
  const anyEstimated = timings.some((t) => t.source === "estimated");
  const total = segments.reduce((a, s) => a + (s.duration_sec ?? 0), 0);

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? segs.error} info={info} />

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>1. Chia đoạn & tạo giọng đọc</h3>
          {busy && <Busy />}
        </div>
        {!gate3 && <Notice kind="warn">Tạo audio là bước tốn chi phí, chỉ mở sau khi duyệt cổng 3 (storyboard & ảnh).</Notice>}
        <p className="doc-muted">
          Lời dẫn chia thành đoạn ~350–900 ký tự. Sửa một câu chỉ tạo lại đoạn chứa nó; các đoạn không đổi dùng lại audio cũ. Cấu hình ElevenLabs ở tab “Cài đặt giọng”.
        </p>
        <div className="doc-row">
          <Field label="Giọng đọc (backend)">
            <select value={backend} onChange={(e) => (setBackend(e.target.value), setEstimate(null))}>
              {(backends.data?.backends ?? []).map((b) => (
                <option key={b} value={b}>
                  {BACKEND_VI[b] ?? b}
                </option>
              ))}
            </select>
          </Field>
          <button
            className="btn"
            disabled={busy !== null}
            onClick={async () => (await run("plan", () => planNarration(id), (r) => `${r.segments} đoạn (${r.created} mới, ${r.kept} giữ nguyên, ${r.removed} bỏ).`)) && refresh()}
          >
            <Layers size={15} /> Chia đoạn
          </button>
          <button
            className="btn"
            disabled={busy !== null || segments.length === 0 || !backend}
            onClick={async () => {
              const e = await run("est", () => estimateNarration(id, backend));
              if (e) setEstimate(e);
            }}
          >
            Ước tính chi phí
          </button>
          <button className="btn btn-primary" disabled={busy !== null || segments.length === 0 || !gate3 || !backend} onClick={() => void generate()}>
            <Mic size={15} /> Tạo audio
          </button>
        </div>
        {estimate && (
          <Notice kind={estimate.paid ? "warn" : "info"}>
            {estimate.segments_to_generate}/{estimate.segments_total} đoạn cần tạo · {estimate.chars} ký tự · chi phí ước tính:{" "}
            <strong>{money(estimate.estimated_cost_usd)}</strong>
            {estimate.paid && " (backend trả phí — sẽ hỏi xác nhận trước khi chạy)"}. Đã chi: ${estimate.spent_usd.toFixed(4)}
            {estimate.spent_unknown_rows > 0 && ` + ${estimate.spent_unknown_rows} lượt gọi chưa biết giá`}
            {estimate.budget_usd !== null && ` · ngân sách $${estimate.budget_usd}`}.
          </Notice>
        )}
        {failed.length > 0 && (
          <Notice kind="error">
            {failed.length} đoạn lỗi: {failed.map((s) => `${s.segment_key} — ${s.error}`).join("; ")}
          </Notice>
        )}

        {segments.length === 0 ? (
          <p className="doc-muted">Chưa chia đoạn. Bấm “Chia đoạn” (cần đã có storyboard).</p>
        ) : (
          <div className="doc-list">
            {segments.map((s) => (
              <div key={s.segment_key} className="doc-item">
                <div className="doc-item-head">
                  <strong>{s.segment_key}</strong>
                  <span className="doc-muted">cảnh {s.scene_keys.join(", ")}</span>
                  <span className="grow" />
                  {s.is_current ? <Badge tone="ok">audio khớp văn bản</Badge> : s.status === "failed" ? <Badge tone="bad">lỗi</Badge> : <Badge tone="muted">chưa có / cũ</Badge>}
                  {s.provider && <Badge tone="muted">{s.provider}</Badge>}
                  {s.duration_sec !== null && <span className="doc-mono doc-muted">{s.duration_sec.toFixed(1)}s</span>}
                  {s.cost_usd !== null && s.cost_usd > 0 && <span className="doc-muted">${s.cost_usd.toFixed(4)}</span>}
                </div>
                <div className="doc-narration">{s.text}</div>
                {s.is_current && <audio controls preload="none" src={segmentAudioUrl(id, s.segment_key, String(s.master_start ?? s.duration_sec))} />}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>2. Master & nghe lại toàn bài</h3>
          <button
            className="btn"
            disabled={busy !== null || !allCurrent}
            onClick={async () => (await run("master", () => buildMaster(id), (r) => `${r.rebuilt ? "Đã ghép" : "Master đã mới"}: ${r.duration_sec.toFixed(1)}s.`)) && refresh()}
          >
            <AudioLines size={15} /> Ghép master
          </button>
        </div>
        {!allCurrent && <p className="doc-muted">Cần audio khớp văn bản cho mọi đoạn trước khi ghép.</p>}
        {allCurrent && (
          <>
            <p className="doc-muted">Tổng {fmtTime(total)} (chưa tính khoảng nghỉ giữa đoạn). Nghe toàn bài trước khi duyệt cổng 4.</p>
            <audio controls preload="none" key={masterTick} src={`${masterAudioUrl(id)}?t=${masterTick}`} />
          </>
        )}
      </div>

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>3. Căn chỉnh timeline theo audio thật</h3>
          {busy === "align" || busy === "assemble" ? <Busy label="Đang căn chỉnh (Whisper trên CPU có thể mất vài phút)…" /> : null}
        </div>
        <p className="doc-muted">
          Thời điểm từng từ lấy từ timestamp của giọng đọc, hoặc Whisper chạy trên máy bạn
          {align.data ? (align.data.whisper_installed ? ` (model “${align.data.whisper_model}”)` : " — CHƯA cài faster-whisper") : ""}. “Ước lượng” chỉ là đoán và luôn bị gắn cờ.
        </p>
        <div className="doc-row">
          <Field label="Phương pháp">
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="auto">Tự động (TTS → Whisper → ước lượng)</option>
              <option value="tts">Chỉ dùng timestamp của TTS</option>
              <option value="whisper">Chỉ dùng Whisper (máy bạn)</option>
              <option value="estimated">Ước lượng (kém chính xác)</option>
            </select>
          </Field>
          <button
            className="btn"
            disabled={busy !== null || !allCurrent}
            onClick={async () => {
              const r = await run("align", () => alignTimeline(id, method), (x) => `Căn chỉnh ${x.aligned.length} đoạn, ${x.cached} đoạn dùng lại kết quả cũ.`);
              if (!r) return;
              (await run("assemble", () => assembleTimeline(id), (x) => `Dựng ${x.scenes} cảnh, ${x.subtitles} phụ đề · ${x.errors} lỗi, ${x.warnings} cảnh báo.`)) && refresh();
            }}
          >
            <Timer size={15} /> Căn chỉnh & dựng timeline
          </button>
        </div>
        {anyEstimated && <Notice kind="warn">Một số cảnh dùng timing ƯỚC LƯỢNG. Hãy nghe lại và chỉnh tay, hoặc căn chỉnh bằng Whisper.</Notice>}

        {timings.length === 0 ? (
          <p className="doc-muted">Chưa có timeline.</p>
        ) : (
          <div className="doc-table-wrap">
            <table className="doc-table">
              <thead>
                <tr>
                  <th>Cảnh</th>
                  <th>Từ → Đến</th>
                  <th>Dài</th>
                  <th>Nguồn timing</th>
                  <th>Khớp từ</th>
                  <th>Bắt đầu (giây)</th>
                </tr>
              </thead>
              <tbody>
                {timings.map((t) => (
                  <tr key={t.scene_key}>
                    <td>
                      <strong>{t.scene_key}</strong>
                      {t.needs_review && <div><Badge tone="warn">cần duyệt</Badge></div>}
                    </td>
                    <td className="doc-mono">
                      {fmtTime(t.start)} → {fmtTime(t.end)}
                    </td>
                    <td className="doc-mono">{t.duration.toFixed(1)}s</td>
                    <td>
                      <Badge tone={SOURCE_VI[t.source].tone}>{SOURCE_VI[t.source].label}</Badge>
                    </td>
                    <td className="doc-mono">{Math.round(t.coverage * 100)}%</td>
                    <td>
                      <SceneStartEditor projectId={id} t={t} onDone={refresh} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="doc-muted">Cảnh đầu tiên của mỗi đoạn audio bắt đầu cùng đoạn đó nên không chỉnh được; chỉnh ranh giới ở cảnh sau nó.</p>
      </div>

      <div className="doc-card">
        <div className="doc-card-head">
          <h3>4. Phụ đề ({subs.data?.length ?? 0})</h3>
          <div className="doc-actions">
            <button className="btn doc-btn-sm" onClick={() => setShowSubs((v) => !v)} disabled={!subs.data?.length}>
              {showSubs ? "Ẩn" : "Xem"}
            </button>
            {subs.data && subs.data.length > 0 && (
              <a className="btn doc-btn-sm" href={srtUrl(id)}>
                <Download size={13} /> Tải SRT
              </a>
            )}
          </div>
        </div>
        {showSubs && (
          <div className="doc-table-wrap" style={{ maxHeight: 360, overflow: "auto" }}>
            <table className="doc-table">
              <tbody>
                {subs.data?.map((s) => (
                  <tr key={s.order_index}>
                    <td className="doc-mono">{s.order_index}</td>
                    <td className="doc-mono">
                      {fmtTime(s.start)} → {fmtTime(s.end)}
                    </td>
                    <td>{s.text}</td>
                    <td className="doc-muted">{s.scene_key}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ReviewBox review={review.data} title="Kiểm tra cổng 4 (audio, timing, phụ đề)" />
    </div>
  );
}
