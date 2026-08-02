import { useState } from "react";
import { Search, Loader2, CheckCircle2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { VideoResultCard } from "../components/VideoResultCard";
import { ChannelVideoTable } from "../components/ChannelVideoTable";
import { detectUrl } from "../api/detect";
import { enqueueDownload } from "../api/downloads";
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
      const analyzed = await detectUrl(url.trim());
      setResult(analyzed);
      setStatus("idle");
    } catch {
      setErrorMessage("Không phân tích được URL này. Kiểm tra lại đường dẫn.");
      setStatus("error");
    }
  }

  function reportQueueOutcome(outcomes: PromiseSettledResult<void>[]) {
    const succeeded = outcomes.filter((o) => o.status === "fulfilled").length;
    const alreadyDownloaded = outcomes.filter(
      (o) => o.status === "rejected" && String((o.reason as Error)?.message ?? "").includes("already downloaded"),
    ).length;
    const failed = outcomes.length - succeeded - alreadyDownloaded;

    const parts = [`Đã thêm ${succeeded}/${outcomes.length} video vào hàng đợi tải.`];
    if (alreadyDownloaded > 0) parts.push(`${alreadyDownloaded} video đã tải trước đó.`);
    if (failed > 0) parts.push(`${failed} video lỗi.`);
    const text = parts.join(" ");

    if (succeeded === 0 && alreadyDownloaded === 0) {
      setErrorMessage(text);
      setStatus("error");
    } else {
      setQueuedMessage(text);
      setStatus("idle");
    }
  }

  async function handleDownloadSingle() {
    if (!result || result.contentType !== "video") return;
    setErrorMessage(null);
    setQueuedMessage(null);
    try {
      await enqueueDownload(result.platform, result.video);
      setQueuedMessage("Đã thêm 1 video vào hàng đợi tải.");
      setStatus("idle");
    } catch (err) {
      if (err instanceof Error && err.message.includes("already downloaded")) {
        setQueuedMessage("Video này đã được tải trước đó.");
        setStatus("idle");
      } else {
        setErrorMessage("Không thêm được video vào hàng đợi tải.");
        setStatus("error");
      }
    }
  }

  async function handleDownloadAll(limit: number) {
    if (!result || result.contentType === "video") return;
    setErrorMessage(null);
    setQueuedMessage(null);
    const outcomes = await Promise.allSettled(
      result.videos.slice(0, limit).map((video) => enqueueDownload(result.platform, video)),
    );
    reportQueueOutcome(outcomes);
  }

  async function handleDownloadSelected(videoIds: string[]) {
    if (!result || result.contentType === "video") return;
    setErrorMessage(null);
    setQueuedMessage(null);
    const selected = result.videos.filter((video) => videoIds.includes(video.id));
    const outcomes = await Promise.allSettled(selected.map((video) => enqueueDownload(result.platform, video)));
    reportQueueOutcome(outcomes);
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
