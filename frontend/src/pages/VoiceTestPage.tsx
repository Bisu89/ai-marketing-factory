import { useEffect, useRef, useState } from "react";
import { AudioLines, Download, Loader2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { getVoiceTestJob, listTestVoices, startVoiceTest, voiceTestAudioUrl } from "../api/voiceTest";
import type { TestVoice, VoiceTestJob } from "../api/voiceTest";
import "./VoiceTestPage.css";

const FALLBACK_VOICE: TestVoice = { id: "vi-VN-HoaiMyNeural", label: "Tiếng Việt — Hoài My (nữ)", language: "vi" };
const POLL_MS = 2000;

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function VoiceTestPage() {
  const [text, setText] = useState("");
  const [voices, setVoices] = useState<TestVoice[]>([FALLBACK_VOICE]);
  const [voice, setVoice] = useState(FALLBACK_VOICE.id);
  const [speed, setSpeed] = useState(1.0);

  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<VoiceTestJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    listTestVoices()
      .then((data) => {
        setVoices(data.voices);
        setVoice(data.default);
      })
      .catch(() => undefined);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  const running = job?.status === "running";

  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [running]);

  const words = text.split(/\s+/).filter((w) => w && !w.startsWith("##")).length;
  const canSubmit = text.trim().length > 0 && !running;

  async function handleSubmit() {
    if (!canSubmit) return;
    if (pollRef.current) window.clearInterval(pollRef.current);
    setError(null);
    setJob({ status: "running" });
    setJobId(null);
    setStartedAt(Date.now());
    setNow(Date.now());
    try {
      const { job_id } = await startVoiceTest(text, voice, speed);
      setJobId(job_id);
      pollRef.current = window.setInterval(async () => {
        try {
          const status = await getVoiceTestJob(job_id);
          setJob(status);
          if (status.status !== "running" && pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Mất kết nối khi kiểm tra tiến độ.");
        }
      }, POLL_MS);
    } catch (err) {
      setJob(null);
      setError(err instanceof Error ? err.message : "Không bắt đầu được.");
    }
  }

  const elapsed = startedAt ? Math.max(0, Math.round((now - startedAt) / 1000)) : 0;

  return (
    <div className="voice-test-page">
      <PageHeader
        title="Thử giọng đọc"
        subtitle="Dán truyện, chọn giọng và tốc độ -- tự đọc và xuất file MP3. Dòng bắt đầu bằng ## (ghi chú cảnh) tự bị bỏ qua."
      />

      <div className="voice-test-form">
        <label className="voice-test-field">
          <span>Nội dung truyện</span>
          <textarea
            rows={14}
            placeholder="Dán truyện vào đây..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <small>
            {words.toLocaleString()} từ · ước tính ~{formatDuration(words / 3.6 / speed)} khi đọc giọng tiếng Việt
          </small>
        </label>

        <div className="voice-test-row">
          <label className="voice-test-field">
            <span>Giọng đọc</span>
            <select value={voice} onChange={(e) => setVoice(e.target.value)}>
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </label>

          <label className="voice-test-field">
            <span>Tốc độ: {speed.toFixed(2)}x</span>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.05}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            />
            <small>
              <button type="button" className="voice-test-link" onClick={() => setSpeed(1)}>
                Về 1.00x
              </button>
            </small>
          </label>
        </div>

        <button className="voice-test-submit" onClick={handleSubmit} disabled={!canSubmit}>
          {running ? <Loader2 size={16} className="spin" /> : <AudioLines size={16} />}
          {running ? `Đang đọc... ${formatDuration(elapsed)}` : "Đọc & xuất MP3"}
        </button>

        {error && <p className="voice-test-error">{error}</p>}
        {job?.status === "error" && <p className="voice-test-error">{job.error}</p>}

        {job?.status === "done" && jobId && (
          <div className="voice-test-result">
            <div>
              <strong>{job.filename}</strong> · dài {formatDuration(job.duration_sec ?? 0)} · xử lý {job.elapsed_sec}s
            </div>
            <audio controls src={voiceTestAudioUrl(jobId)} />
            <a className="voice-test-download" href={voiceTestAudioUrl(jobId, true)}>
              <Download size={15} /> Tải MP3
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
