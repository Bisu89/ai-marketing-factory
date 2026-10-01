import { useEffect, useState } from "react";
import { Loader2, ImageDown } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { fetchManhuaChapter, getManhuaFetchLog } from "../api/manhua";
import type { ManhuaFetchLogEntry, ManhuaFetchResult } from "../api/manhua";
import "./ManhuaFetchPage.css";

// A chapter URL ends in .../chuong-N or .../chapter-N (or -chapter-N.html) --
// used only to suggest a folder name, matching tools/manhua_recap/recap.py's
// own dqg_epN convention (see manhua-series/*/SERIES.md).
function suggestChapterDir(url: string): string {
  const match = url.match(/\/([a-z0-9-]+)\/(?:chuong|chapter)-(\d+)/i);
  if (!match) return "";
  const [, slug, n] = match;
  const short = slug.split("-").map((w) => w[0]).join("").slice(0, 4) || slug.slice(0, 8);
  return `${short}_ep${n}`;
}

function relativeTime(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "vừa xong";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút trước`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} giờ trước`;
  return `${Math.floor(seconds / 86400)} ngày trước`;
}

export function ManhuaFetchPage() {
  const [url, setUrl] = useState("");
  const [chapterDir, setChapterDir] = useState("");
  const [dirTouched, setDirTouched] = useState(false);
  const [count, setCount] = useState(1);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ManhuaFetchResult | null>(null);

  const [log, setLog] = useState<ManhuaFetchLogEntry[]>([]);
  const [logLoading, setLogLoading] = useState(true);

  function loadLog() {
    getManhuaFetchLog()
      .then(setLog)
      .catch(() => setLog([]))
      .finally(() => setLogLoading(false));
  }

  useEffect(loadLog, []);

  function handleUrlChange(value: string) {
    setUrl(value);
    if (!dirTouched) setChapterDir(suggestChapterDir(value));
  }

  const canSubmit = url.trim().length > 0 && chapterDir.trim().length > 0 && !submitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchManhuaChapter(url.trim(), chapterDir.trim(), count);
      setResult(data);
      loadLog();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được chương này.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="manhua-fetch-page">
      <PageHeader
        title="Tải chương truyện"
        subtitle="Dán link một chương -- trang tự tải ảnh về manhua-recap/, tự bỏ qua ảnh quảng cáo/cấm reup lặp lại."
      />

      <div className="manhua-fetch-form">
        <label className="manhua-fetch-field">
          <span>Link chương</span>
          <input
            type="text"
            placeholder="https://www.zettruyen2.com/truyen-tranh/<truyện>/chuong-N"
            value={url}
            onChange={(e) => handleUrlChange(e.target.value)}
          />
        </label>

        <div className="manhua-fetch-row">
          <label className="manhua-fetch-field">
            <span>Thư mục lưu (trong manhua-recap/)</span>
            <input
              type="text"
              placeholder="vd: dqg_ep12"
              value={chapterDir}
              onChange={(e) => {
                setChapterDir(e.target.value);
                setDirTouched(true);
              }}
            />
          </label>

          <label className="manhua-fetch-field manhua-fetch-count">
            <span>Số chương cần tải</span>
            <input
              type="number"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            />
          </label>
        </div>

        <p className="manhua-fetch-hint">
          Hỗ trợ manhuavn2.com, cotruyenday.com, zettruyen*.com, truyenqq.com.vn. Số chương &gt; 1 sẽ tải chương này và các chương kế
          tiếp (link phải kết thúc bằng chuong-N / chapter-N).
        </p>

        <button className="manhua-fetch-submit" onClick={handleSubmit} disabled={!canSubmit}>
          {submitting ? <Loader2 size={16} className="spin" /> : <ImageDown size={16} />}
          {submitting ? "Đang tải..." : "Tải chương"}
        </button>

        {error && <p className="manhua-fetch-error">{error}</p>}

        {result && (
          <div className="manhua-fetch-result">
            <strong>{result.total_saved} trang</strong> đã lưu vào <code>manhua-recap/{result.chapter_dir}/</code>
            {result.total_skipped > 0 && <> · bỏ qua {result.total_skipped} ảnh quảng cáo/lặp lại</>}
            {result.chapters.length > 1 && (
              <ul className="manhua-fetch-chapters">
                {result.chapters.map((c) => (
                  <li key={c.n ?? Math.random()}>
                    Chương {c.n}: {c.saved} trang{c.skipped > 0 && ` (bỏ ${c.skipped})`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <h2 className="manhua-fetch-log-title">Lịch sử tải</h2>
      {logLoading ? (
        <p className="manhua-fetch-hint">Đang tải lịch sử...</p>
      ) : log.length === 0 ? (
        <EmptyState icon={ImageDown} title="Chưa có lần tải nào" description="Lịch sử các lần tải sẽ hiện ở đây." />
      ) : (
        <table className="manhua-fetch-log-table">
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Link</th>
              <th>Thư mục</th>
              <th>Số chương</th>
              <th>Kết quả</th>
            </tr>
          </thead>
          <tbody>
            {log.map((entry) => (
              <tr key={entry.id} className={entry.error ? "manhua-fetch-log-row-error" : undefined}>
                <td title={entry.created_at}>{relativeTime(entry.created_at)}</td>
                <td className="manhua-fetch-log-url" title={entry.url}>
                  {entry.url}
                </td>
                <td>{entry.chapter_dir}</td>
                <td>{entry.count}</td>
                <td>
                  {entry.error ? (
                    entry.error
                  ) : (
                    <>
                      {entry.saved} trang
                      {entry.skipped > 0 && `, bỏ ${entry.skipped}`}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
