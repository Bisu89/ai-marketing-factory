import { useState } from "react";
import { Search, Loader2, CheckCircle2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { VideoResultCard } from "../components/VideoResultCard";
import { ChannelVideoTable } from "../components/ChannelVideoTable";
import { analyzeUrl } from "../mock/analyzeUrl";
import type { AnalyzeResult } from "../types/video";
import "./DownloadPage.css";

type Status = "idle" | "loading" | "error";

export function DownloadPage() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [queuedMessage, setQueuedMessage] = useState<string | null>(null);

  async function handleAnalyze() {
    if (!url.trim()) return;

    setStatus("loading");
    setErrorMessage(null);
    setResult(null);
    setQueuedMessage(null);

    try {
      const analyzed = await analyzeUrl(url.trim());
      setResult(analyzed);
      setStatus("idle");
    } catch {
      setErrorMessage("Không phân tích được URL này. Kiểm tra lại đường dẫn.");
      setStatus("error");
    }
  }

  function handleDownloadSingle() {
    setQueuedMessage("Đã thêm 1 video vào hàng đợi tải.");
  }

  function handleDownloadAll(limit: number) {
    setQueuedMessage(`Đã thêm ${limit} video vào hàng đợi tải.`);
  }

  function handleDownloadSelected(videoIds: string[]) {
    setQueuedMessage(`Đã thêm ${videoIds.length} video đã chọn vào hàng đợi tải.`);
  }

  return (
    <>
      <PageHeader title="Download" subtitle="Dán URL từ YouTube, TikTok, Facebook, Instagram để phân tích và tải về" />

      <div className="download-input-row">
        <input
          className="download-url-input"
          type="text"
          placeholder="Dán URL video, playlist hoặc channel..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
        />
        <button className="btn btn-primary" onClick={handleAnalyze} disabled={!url.trim() || status === "loading"}>
          {status === "loading" ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
          Analyze
        </button>
      </div>

      {status === "error" && <div className="download-alert download-alert-error">{errorMessage}</div>}

      {queuedMessage && (
        <div className="download-alert download-alert-success">
          <CheckCircle2 size={16} />
          {queuedMessage}
        </div>
      )}

      {result?.contentType === "video" && (
        <VideoResultCard platform={result.platform} video={result.video} onDownload={handleDownloadSingle} />
      )}

      {result && result.contentType !== "video" && (
        <ChannelVideoTable
          platform={result.platform}
          contentType={result.contentType}
          title={result.title}
          author={result.author}
          videos={result.videos}
          onDownloadAll={handleDownloadAll}
          onDownloadSelected={handleDownloadSelected}
        />
      )}
    </>
  );
}
