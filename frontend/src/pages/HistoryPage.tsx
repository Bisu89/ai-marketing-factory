import { useEffect, useState } from "react";
import { History, FolderOpen } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { PlatformBadge } from "../components/PlatformBadge";
import { listDownloads, openDownloadFolder } from "../api/downloads";
import type { DownloadTask, DownloadStatus } from "../types/download";
import type { Platform } from "../types/video";
import "./HistoryPage.css";

const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL: Record<DownloadStatus, string> = {
  queued: "Trong hàng đợi",
  downloading: "Đang tải",
  paused: "Tạm dừng",
  completed: "Hoàn tất",
  failed: "Lỗi",
  cancelled: "Đã huỷ",
};

function statusText(task: DownloadTask): string {
  if (task.status === "downloading") {
    const pct = task.progress_pct != null ? Math.round(task.progress_pct) : null;
    return pct != null ? `Đang tải ${pct}%` : "Đang tải";
  }
  return STATUS_LABEL[task.status];
}

export function HistoryPage() {
  const [tasks, setTasks] = useState<DownloadTask[]>([]);
  const [openError, setOpenError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await listDownloads();
        if (!cancelled) setTasks(data);
      } catch {
        // Bỏ qua lỗi mạng tạm thời của một lượt poll, thử lại ở lượt sau.
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handleOpenFolder(taskId: number) {
    setOpenError(null);
    try {
      await openDownloadFolder(taskId);
    } catch {
      setOpenError("Không mở được thư mục.");
    }
  }

  return (
    <>
      <PageHeader title="History" subtitle="Lịch sử các lượt tải, bao gồm cả lượt lỗi" />

      {openError && <div className="history-alert history-alert-error">{openError}</div>}

      {tasks.length === 0 ? (
        <EmptyState
          icon={History}
          title="Chưa có lịch sử"
          description="Các lượt tải (thành công hoặc lỗi) sẽ được ghi lại tại đây."
        />
      ) : (
        <div className="history-table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Trạng thái</th>
                <th>Vị trí file</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <div className="history-video-cell">
                      {task.video.thumbnail_url && <img src={task.video.thumbnail_url} alt="" />}
                      <div>
                        <div className="history-video-title">{task.video.title}</div>
                        <PlatformBadge platform={task.video.platform as Platform} />
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`history-status history-status--${task.status}`}>{statusText(task)}</span>
                    {task.status === "failed" && task.error_message && (
                      <div className="history-error-message">{task.error_message}</div>
                    )}
                  </td>
                  <td>
                    {task.status === "completed" && task.video.video_path ? (
                      <div className="history-folder-cell">
                        <button className="btn btn-secondary" onClick={() => handleOpenFolder(task.id)}>
                          <FolderOpen size={14} />
                          Mở thư mục
                        </button>
                        <span className="history-path">{task.video.video_path}</span>
                      </div>
                    ) : (
                      <span className="history-path history-path-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
