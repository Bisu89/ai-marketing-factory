import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { getElevenLabsSettings, saveElevenLabsSettings } from "../../api/documentary";
import type { ElevenLabsSettings } from "../../api/documentary";
import { ActionFeedback, Badge, Field, Loading, useAction, useLoader } from "./shared";

type Draft = {
  api_key: string;
  voice_id: string;
  model_id: string;
  stability: string;
  similarity_boost: string;
  style: string;
  speed: string;
  usd_per_1k_chars: string;
};

function toDraft(s: ElevenLabsSettings): Draft {
  return {
    api_key: "",
    voice_id: s.voice_id ?? "",
    model_id: s.model_id,
    stability: String(s.stability),
    similarity_boost: String(s.similarity_boost),
    style: String(s.style),
    speed: String(s.speed),
    usd_per_1k_chars: s.usd_per_1k_chars === null ? "" : String(s.usd_per_1k_chars),
  };
}

export function VoiceSettingsTab() {
  const loaded = useLoader(getElevenLabsSettings, "elevenlabs");
  const { busy, error, info, run } = useAction();
  const [d, setD] = useState<Draft | null>(null);

  useEffect(() => {
    if (loaded.data) setD(toDraft(loaded.data));
  }, [loaded.data]);

  if (loaded.loading || !d) return <Loading />;
  const cur = loaded.data!;
  const set = (k: keyof Draft, v: string) => setD({ ...d, [k]: v });

  async function save() {
    if (!d) return;
    const body: Record<string, string | number> = {};
    const base = toDraft(cur);
    // Only send what changed; the API key is send-only (never shown back) so a blank box means "leave as is".
    if (d.api_key.trim()) body.api_key = d.api_key.trim();
    for (const k of ["voice_id", "model_id"] as const) if (d[k].trim() && d[k].trim() !== base[k]) body[k] = d[k].trim();
    for (const k of ["stability", "similarity_boost", "style", "speed", "usd_per_1k_chars"] as const) {
      if (d[k].trim() !== "" && d[k] !== base[k]) {
        const n = Number(d[k]);
        if (!Number.isFinite(n)) {
          await run("save", () => Promise.reject(new Error(`Giá trị “${k}” phải là số.`)));
          return;
        }
        body[k] = n;
      }
    }
    if (Object.keys(body).length === 0) {
      await run("save", () => Promise.reject(new Error("Không có thay đổi nào để lưu.")));
      return;
    }
    const r = await run("save", () => saveElevenLabsSettings(body), () => "Đã lưu cấu hình ElevenLabs.");
    if (r) {
      setD({ ...toDraft(r), api_key: "" });
      void loaded.reload();
    }
  }

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? loaded.error} info={info} />
      <form
        className="doc-card"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="doc-card-head">
          <h3>Giọng đọc ElevenLabs</h3>
          {cur.ready ? <Badge tone="ok">Sẵn sàng</Badge> : <Badge tone="warn">Chưa đủ key + voice ID</Badge>}
        </div>
        <p className="doc-muted">
          Key được lưu trên máy và chỉ server dùng; giao diện không bao giờ hiển thị lại key. Voice ID lấy trong tài khoản ElevenLabs của bạn (hệ thống không
          đoán trước). Nếu không muốn trả phí, dùng backend “edge” (miễn phí) ở tab Giọng đọc.
        </p>
        <div className="doc-row">
          <Field label={`API key ${cur.has_api_key ? "(đã lưu — để trống nếu giữ nguyên)" : "(chưa có)"}`}>
            <input type="password" autoComplete="off" value={d.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder={cur.has_api_key ? "••••••••" : "sk_…"} />
          </Field>
          <Field label="Voice ID">
            <input value={d.voice_id} onChange={(e) => set("voice_id", e.target.value)} />
          </Field>
          <Field label="Model ID">
            <input value={d.model_id} onChange={(e) => set("model_id", e.target.value)} />
          </Field>
        </div>
        <div className="doc-row">
          <Field label="Stability (0–1)">
            <input value={d.stability} onChange={(e) => set("stability", e.target.value)} inputMode="decimal" />
          </Field>
          <Field label="Similarity boost (0–1)">
            <input value={d.similarity_boost} onChange={(e) => set("similarity_boost", e.target.value)} inputMode="decimal" />
          </Field>
          <Field label="Style (0–1)">
            <input value={d.style} onChange={(e) => set("style", e.target.value)} inputMode="decimal" />
          </Field>
          <Field label="Tốc độ (0.7–1.2)">
            <input value={d.speed} onChange={(e) => set("speed", e.target.value)} inputMode="decimal" />
          </Field>
        </div>
        <Field
          label="Giá theo gói của bạn (USD / 1000 ký tự)"
          hint="Không có giá mặc định vì mỗi gói khác nhau. Để trống = chi phí hiển thị “chưa biết”, ngân sách không áp dụng được cho audio ElevenLabs."
        >
          <input value={d.usd_per_1k_chars} onChange={(e) => set("usd_per_1k_chars", e.target.value)} inputMode="decimal" placeholder="VD: 0.30" />
        </Field>
        <div className="doc-actions">
          <button className="btn btn-primary" type="submit" disabled={busy !== null}>
            <Save size={15} /> {busy ? "Đang lưu…" : "Lưu cấu hình"}
          </button>
        </div>
        <p className="doc-muted">Đổi giọng hoặc thông số sẽ làm audio đã tạo bị đánh dấu cũ (cần tạo lại các đoạn đó).</p>
      </form>
    </div>
  );
}
