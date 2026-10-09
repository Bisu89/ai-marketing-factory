import { FolderOpen, PackageCheck } from "lucide-react";
import { exportProject, listExports, openExportFolder } from "../../api/documentary";
import { ActionFeedback, Badge, Loading, Notice, useAction, useLoader } from "./shared";
import type { TabProps } from "./shared";

const FILE_NOTES: Record<string, string> = {
  "video.mp4": "bản render cuối đã kiểm tra (sao chép, không mã hóa lại)",
  "subtitles.srt": "phụ đề đã duyệt",
  "credits.json": "ghi công/giấy phép từng ảnh (máy đọc)",
  "credits.txt": "ghi công/giấy phép từng ảnh (người đọc)",
  "sources.json": "nguồn + khẳng định + trạng thái",
  "script.md": "kịch bản đã duyệt, có tham chiếu khẳng định",
  "timeline.json": "cảnh, thời điểm và nguồn timing",
  "description.txt": "mô tả đăng nháp: chương, nguồn, ghi công",
  "manifest.json": "thông tin render + SHA-256 từng file",
};

function mb(bytes: number) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function ExportTab({ project, reloadProject }: TabProps) {
  const id = project.id;
  const exports = useLoader(() => listExports(id), `${id}:${project.updated_at}`);
  const { busy, error, info, run } = useAction();
  const ready = project.state === "approved" || project.state === "exported";

  async function doExport() {
    const r = await run("export", () => exportProject(id), (x) => `Đã xuất ${Object.keys(x.files).length} file.`);
    if (r) {
      await exports.reload();
      reloadProject();
    }
  }

  if (exports.loading) return <Loading />;
  const list = exports.data ?? [];

  return (
    <div className="doc-page">
      <ActionFeedback error={error ?? exports.error} info={info} />
      {!ready && <Notice kind="warn">Chỉ xuất được sau khi duyệt cổng 5 (video cuối). Hiện dự án ở bước “{project.state}”.</Notice>}
      <div className="doc-card">
        <div className="doc-card-head">
          <h3>Gói xuất để đăng</h3>
          <button className="btn btn-primary" disabled={!ready || busy !== null} onClick={() => void doExport()}>
            <PackageCheck size={15} /> {list.length ? "Xuất lại (thư mục mới)" : "Xuất"}
          </button>
        </div>
        <p className="doc-muted">
          Tạo một thư mục gồm video, phụ đề, ghi công ảnh, nguồn, kịch bản, timeline, mô tả nháp và manifest có SHA-256. Chỉ sao chép —
          không đăng đi đâu và không đụng file nào ngoài thư mục xuất. Bản xuất bị từ chối nếu dữ liệu đã đổi sau lần render cuối.
        </p>
      </div>

      {list.length === 0 && <p className="doc-muted">Chưa xuất lần nào.</p>}
      {list.map((e) => (
        <div key={e.id} className="doc-card">
          <div className="doc-card-head">
            <h3>
              Bản xuất #{e.id} <span className="doc-muted">· {new Date(e.created_at).toLocaleString("vi-VN")} · từ render #{e.render_job_id}</span>
            </h3>
            <button className="btn doc-btn-sm" onClick={async () => void (await run("open", () => openExportFolder(id, e.id)))}>
              <FolderOpen size={13} /> Mở thư mục
            </button>
          </div>
          <code className="doc-muted" style={{ wordBreak: "break-all" }}>{e.path}</code>
          {e.warnings.length > 0 && (
            <div>
              <Badge tone="warn">{e.warnings.length} điều cần xem trước khi đăng</Badge>
              <ul className="doc-issues">
                {e.warnings.map((w, i) => (
                  <li key={i} className="doc-issue-warn">
                    {w.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="doc-table-wrap">
            <table className="doc-table">
              <tbody>
                {Object.entries(e.files).map(([name, meta]) => (
                  <tr key={name}>
                    <td>
                      <strong>{name}</strong>
                    </td>
                    <td className="doc-muted">{FILE_NOTES[name] ?? ""}</td>
                    <td className="doc-mono">{mb(meta.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
