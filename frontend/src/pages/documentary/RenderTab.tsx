import { useEffect, useState } from "react";
import { Clapperboard, Film, Play, X } from "lucide-react";
import {
  cancelRender,
  getGateReview,
  listRenderJobs,
  PHASE_LABELS,
  renderLogUrl,
  renderPreflight,
  renderTools,
  renderVideoUrl,
  startRender,
} from "../../api/documentary";
import type { RenderJob } from "../../api/documentary";
import { ActionFeedback, Badge, Field, Loading, Notice, ReviewBox, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const STATUS_VI: Record<RenderJob["status"], { label: string; tone: "ok" | "warn" | "bad" | "muted" | "info" }> = {
  queued: { label: "Đang chờ", tone: "muted" },
  running: { label: "Đang render", tone: "info" },
  succeeded: { label: "Xong", tone: "ok" },
  failed: { label: "Lỗi", tone: "bad" },
  cancelled: { label: "Đã hủy", tone: "muted" },
};

const SECONDS = [
  { v: "15", label: "15 giây đầu" },
  { v: "30", label: "30 giây đầu" },
  { v: "60", label: "60 giây đầu" },
  { v: "", label: "Toàn bộ video" },
];
const SCALES = [
  { v: "0.25", label: "Rất nhỏ (480×270) — nhanh nhất" },
  { v: "0.5", label: "Nhỏ (960×540)" },
  { v: "0.75", label: "Vừa (1440×810)" },
];

function JobProgress({ job, onCancel, busy }: { job: RenderJob; onCancel: () => void; busy: boolean }) {
  return (
    <div className="doc-card">
      <div className="doc-card-head">
        <h3>
          Job #{job.id} · {job.kind === "final" ? "bản cuối" : "preview"}
        </h3>
        <button className="btn doc-btn-sm doc-btn-danger" disabled={busy} onClick={onCancel}>
          <X size={13} /> Hủy
        </button>
      </div>
      <div className="doc-progress" role="progressbar" aria-valuenow={Math.round(job.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: `${Math.round(job.progress * 100)}%` }} />
      </div>
      <div className="doc-muted">
        {job.status === "queued" ? "Đang chờ tới lượt (mỗi lần chỉ render một video)" : PHASE_LABELS[job.phase ?? ""] ?? job.phase} · {Math.round(job.progress * 100)}%
      </div>
    </div>
  );
}

export function RenderTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const stamp = `${id}:${project.updated_at}`;
  const pre = useLoader(() => renderPreflight(id), stamp);
  const tools = useLoader(renderTools, "tools");
  const jobs = useLoader(() => listRenderJobs(id), id);
  const review = useLoader(() => getGateReview(id, "final"), stamp);
  const { busy, error, info, run, notify } = useAction();

  const [seconds, setSeconds] = useState("30");
  const [scale, setScale] = useState("0.5");
  const [theme, setTheme] = useState<"collage" | "cinematic" | "poster">("collage");
  const [musicPath, setMusicPath] = useState("");
  const [musicDb, setMusicDb] = useState("-24");
  const [musicCredit, setMusicCredit] = useState("");
  const [burn, setBurn] = useState(true);
  const [gray, setGray] = useState(false);
  const [normalize, setNormalize] = useState(true);
  const [playing, setPlaying] = useState<number | null>(null);
  const [logFor, setLogFor] = useState<{ id: number; text: string } | null>(null);

  const list = jobs.data ?? [];
  const active = list.find((j) => j.status === "queued" || j.status === "running");

  // Poll while something is rendering; on completion refresh the project (a final render supersedes earlier approvals).
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => void jobs.reload(), 2000);
    return () => window.clearInterval(t);
  }, [active?.id, active?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const activeId = active?.id ?? null;
  const [prevActive, setPrevActive] = useState<number | null>(null);
  useEffect(() => {
    if (prevActive !== null && activeId === null) {
      reloadProject();
      void review.reload();
      const finished = list.find((j) => j.id === prevActive);
      if (finished?.has_output) setPlaying(finished.id); // show the video that just finished
    }
    setPrevActive(activeId);
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function start(kind: "preview" | "final") {
    if (kind === "final" && !window.confirm("Render bản cuối 1920×1080 cho toàn bộ video. Việc này chiếm CPU và có thể mất nhiều phút. Tiếp tục?")) return;
    const music = musicPath.trim()
      ? { music_path: musicPath.trim(), music_db: Number(musicDb), music_credit: musicCredit.trim() || null }
      : {};
    const body =
      kind === "final"
        ? { kind, theme, grayscale: gray, burn_subtitles: burn, normalize_audio: normalize, ...music }
        : { kind, theme, grayscale: gray, scale: Number(scale), seconds: seconds === "" ? null : Number(seconds), burn_subtitles: burn, normalize_audio: normalize, ...music };
    const job = await run("start", () => startRender(id, body));
    if (!job) return;
    if (job.reused) notify("Đầu vào không đổi so với lần render trước — dùng lại kết quả, không render lại.");
    await jobs.reload();
    if (job.status === "succeeded") setPlaying(job.id);
  }

  async function showLog(j: RenderJob) {
    try {
      const text = await (await fetch(renderLogUrl(id, j.id))).text();
      setLogFor({ id: j.id, text });
    } catch {
      setLogFor({ id: j.id, text: "Không đọc được log." });
    }
  }

  if (jobs.loading || pre.loading) return <Loading />;
  const gate4 = project.gates.find((g) => g.gate === "narration_timing")?.status === "approved";
  const canRender = !!pre.data?.ok && !active;
  const playJob = list.find((j) => j.id === playing && j.has_output);

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? jobs.error} info={info} />

      <div className="doc-card">
        <h3>Điều kiện để render</h3>
        {!gate4 && <Notice kind="warn">Cần duyệt cổng 4 (narration & timing) trước khi render.</Notice>}
        {tools.data && Object.entries(tools.data).some(([, ok]) => !ok) && (
          <Notice kind="error">
            Thiếu công cụ: {Object.entries(tools.data).filter(([, ok]) => !ok).map(([n]) => n).join(", ")} — cần cài Node.js và ffmpeg.
          </Notice>
        )}
        <ReviewBox review={pre.data ? { ...pre.data, warnings: [] } : null} title="Kiểm tra trước khi render" />
        <p className="doc-muted">
          Hình ảnh dựng bằng Remotion từ ảnh đã duyệt và timeline thật; chữ trên màn hình do code vẽ (lấy từ chính lời dẫn hoặc phần bạn nhập ở tab
          Storyboard), nên không bị sai chính tả như chữ nhúng trong ảnh AI. Tiếng ghép bằng ffmpeg từ narration master.
        </p>
      </div>

      <div className="doc-card">
        <h3>Phong cách hình ảnh</h3>
        <div className="doc-row">
          <Field label="Chủ đề" hint="Áp dụng cho cả preview và bản cuối.">
            <select value={theme} onChange={(e) => setTheme(e.target.value as "collage" | "cinematic" | "poster")}>
              <option value="collage">Collage giấy cắt dán (mặc định) — khung giấy rách, băng keo, chữ cắt dán, số lớn</option>
            </select>
          </Field>
        </div>
      </div>

      <div className="doc-card">
        <h3>Nhạc nền (tùy chọn)</h3>
        <p className="doc-muted">
          Bạn tự cung cấp file nhạc <strong>miễn phí bản quyền</strong> (mp3, wav, m4a, ogg, flac). Nhạc được lặp lại cho đủ độ dài, tự hạ nhỏ khi có giọng đọc
          và nhỏ dần ở 3 giây cuối. Để trống = không có nhạc.
        </p>
        <div className="doc-row">
          <Field label="Đường dẫn file nhạc (đầy đủ)">
            <input value={musicPath} onChange={(e) => setMusicPath(e.target.value)} placeholder="C:\Users\bạn\Music\nen.mp3" />
          </Field>
          <Field label="Mức nhạc (dB, trước khi hạ)">
            <select value={musicDb} onChange={(e) => setMusicDb(e.target.value)}>
              <option value="-30">-30 (rất nhỏ)</option>
              <option value="-24">-24 (mặc định)</option>
              <option value="-18">-18 (rõ hơn)</option>
              <option value="-12">-12 (to)</option>
            </select>
          </Field>
        </div>
        <Field label="Giấy phép / ghi công của bản nhạc" hint="Sẽ ghi vào mô tả và credits khi xuất. Bắt buộc nên điền nếu dùng nhạc.">
          <input value={musicCredit} onChange={(e) => setMusicCredit(e.target.value)} placeholder="VD: 'Tên bài' — Tác giả, CC0, nguồn" />
        </Field>
      </div>

      <div className="doc-card">
        <h3>Render preview (nhanh, để xem thử)</h3>
        <div className="doc-row">
          <Field label="Phần video">
            <select value={seconds} onChange={(e) => setSeconds(e.target.value)}>
              {SECONDS.map((s) => (
                <option key={s.v} value={s.v}>
                  {s.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Kích thước">
            <select value={scale} onChange={(e) => setScale(e.target.value)}>
              {SCALES.map((s) => (
                <option key={s.v} value={s.v}>
                  {s.label}
                </option>
              ))}
            </select>
          </Field>
          <label className="doc-check">
            <input type="checkbox" checked={burn} onChange={(e) => setBurn(e.target.checked)} /> Ghi phụ đề lên hình
          </label>
          <label className="doc-check">
            <input type="checkbox" checked={gray} onChange={(e) => setGray(e.target.checked)} /> Ảnh đen trắng (cho ảnh tư liệu cổ; bỏ chọn nếu ảnh màu)
          </label>
          <label className="doc-check">
            <input type="checkbox" checked={normalize} onChange={(e) => setNormalize(e.target.checked)} /> Chuẩn hóa âm lượng
          </label>
        </div>
        <div className="doc-actions">
          <button className="btn btn-primary" disabled={!canRender || busy !== null || !gate4} onClick={() => void start("preview")}>
            <Clapperboard size={15} /> Render preview
          </button>
          <button className="btn" disabled={!canRender || busy !== null || !gate4} onClick={() => void start("final")}>
            <Film size={15} /> Render bản cuối 1080p
          </button>
        </div>
        <p className="doc-muted">Bản cuối luôn là 1920×1080, 30 fps, đủ độ dài, và được kiểm tra (độ phân giải, fps, tiếng, khung hình đen) trước khi tính là đạt.</p>
      </div>

      {active && <JobProgress job={active} busy={busy !== null} onCancel={async () => (await run("cancel", () => cancelRender(id, active.id))) && void jobs.reload()} />}

      {playJob && (
        <div className="doc-card">
          <h3>
            Xem job #{playJob.id} ({playJob.kind === "final" ? "bản cuối" : "preview"}
            {playJob.qc?.width ? ` ${playJob.qc.width}×${playJob.qc.height}` : ""})
          </h3>
          <video className="doc-video" controls src={renderVideoUrl(id, playJob.id)} key={playJob.id} />
        </div>
      )}

      <div className="doc-card">
        <h3>Các lần render ({list.length})</h3>
        {list.length === 0 && <p className="doc-muted">Chưa render lần nào.</p>}
        <div className="doc-list">
          {list.map((j) => (
            <div key={j.id} className="doc-item">
              <div className="doc-item-head">
                <strong>#{j.id}</strong>
                <Badge tone={j.kind === "final" ? "info" : "muted"}>{j.kind === "final" ? "bản cuối" : "preview"}</Badge>
                <Badge tone="muted">{j.params.theme === "cinematic" ? "điện ảnh" : j.params.theme === "poster" ? "poster" : "collage"}</Badge>
                <Badge tone={STATUS_VI[j.status].tone}>{STATUS_VI[j.status].label}</Badge>
                {j.qc && (j.qc.ok ? <Badge tone="ok">Đạt kiểm tra</Badge> : <Badge tone="bad">{j.qc.issues.length} lỗi</Badge>)}
                <span className="doc-muted">
                  scale {j.params.scale}
                  {j.params.seconds ? ` · ${j.params.seconds}s đầu` : " · đủ độ dài"} · {new Date(j.created_at).toLocaleString("vi-VN")}
                </span>
                <span className="grow" />
                {j.has_output && (
                  <button className="btn doc-btn-sm" onClick={() => setPlaying(j.id)}>
                    <Play size={12} /> Xem
                  </button>
                )}
                <button className="btn doc-btn-sm" onClick={() => void showLog(j)}>
                  Log
                </button>
              </div>
              {j.error && <div className="doc-issue-bad">{j.error}</div>}
              {j.qc && j.qc.issues.length > 0 && (
                <ul className="doc-issues">
                  {j.qc.issues.map((i, k) => (
                    <li key={k} className="doc-issue-bad">
                      {i.message}
                    </li>
                  ))}
                </ul>
              )}
              {j.qc && j.qc.warnings.length > 0 && (
                <ul className="doc-issues">
                  {j.qc.warnings.map((i, k) => (
                    <li key={k} className="doc-issue-warn">
                      {i.message}
                    </li>
                  ))}
                </ul>
              )}
              {logFor?.id === j.id && (
                <pre style={{ maxHeight: 260, overflow: "auto", fontSize: 12, background: "var(--surface-alt)", padding: 10, borderRadius: 8, whiteSpace: "pre-wrap" }}>
                  {logFor.text || "(log trống)"}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>

      <ReviewBox review={review.data} title="Kiểm tra cổng 5 (video cuối)" />
    </div>
  );
}
