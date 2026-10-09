import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Landmark, Plus, FlaskConical } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { createDemoProject, createProject, listProjects, STATE_LABELS } from "../api/documentary";
import { ActionFeedback, Badge, Field, Loading, useAction, useLoader } from "./documentary/shared";
import "./documentary/documentary.css";

function stateTone(state: string): "ok" | "warn" | "bad" | "muted" | "info" {
  if (state === "failed") return "bad";
  if (state === "exported" || state === "approved") return "ok";
  if (state === "draft") return "muted";
  return "info";
}

export function DocumentaryListPage() {
  const navigate = useNavigate();
  const { data: projects, error: loadError, loading, reload } = useLoader(listProjects, "list");
  const { busy, error, info, run } = useAction();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [budget, setBudget] = useState("");

  async function create() {
    const budgetNum = budget.trim() === "" ? null : Number(budget);
    if (budgetNum !== null && (!Number.isFinite(budgetNum) || budgetNum < 0)) {
      await run("create", () => Promise.reject(new Error("Ngân sách phải là số ≥ 0 (USD), hoặc để trống.")));
      return;
    }
    const created = await run("create", () => createProject({ title, topic, budget_usd: budgetNum }));
    if (created) navigate(`/documentary/${created.id}`);
  }

  async function demo() {
    const created = await run("demo", createDemoProject);
    if (created) navigate(`/documentary/${created.id}`);
  }

  return (
    <div className="doc-page">
      <PageHeader
        title="Phim tài liệu lịch sử"
        subtitle="Từ chủ đề → nghiên cứu có nguồn → kịch bản → storyboard → ảnh → giọng đọc → timeline. Mỗi bước phải được duyệt."
        actions={
          <>
            <button className="btn btn-secondary" onClick={demo} disabled={busy !== null}>
              <FlaskConical size={16} /> Dự án mẫu
            </button>
            <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
              <Plus size={16} /> Dự án mới
            </button>
          </>
        }
      />

      <ActionFeedback error={error} info={info} />

      {showForm && (
        <form
          className="doc-card"
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          <h3>Tạo dự án</h3>
          <div className="doc-row">
            <Field label="Tiêu đề">
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="VD: Sự thất thủ của Constantinople" required />
            </Field>
            <Field label="Ngân sách (USD, tùy chọn)" hint="Chặn tạo audio trả phí nếu ước tính vượt mức này.">
              <input value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" placeholder="VD: 5" />
            </Field>
          </div>
          <Field label="Chủ đề / câu hỏi lịch sử">
            <textarea rows={3} value={topic} onChange={(e) => setTopic(e.target.value)} required placeholder="Chủ đề phim tài liệu muốn làm…" />
          </Field>
          <div className="doc-actions">
            <button className="btn btn-primary" type="submit" disabled={busy !== null || !title.trim() || !topic.trim()}>
              {busy === "create" ? "Đang tạo…" : "Tạo dự án"}
            </button>
            <button className="btn" type="button" onClick={() => setShowForm(false)}>
              Hủy
            </button>
          </div>
        </form>
      )}

      {loading && <Loading />}
      {loadError && <ActionFeedback error={loadError} info={null} />}
      {!loading && projects && projects.length === 0 && !showForm && (
        <EmptyState
          icon={Landmark}
          title="Chưa có dự án nào"
          description="Tạo dự án mới, hoặc mở dự án mẫu để thử luồng làm việc (nội dung mẫu, không phải lịch sử đã kiểm chứng)."
        />
      )}
      {projects && projects.length > 0 && (
        <div className="doc-card doc-table-wrap">
          <table className="doc-table">
            <thead>
              <tr>
                <th>Dự án</th>
                <th>Trạng thái</th>
                <th>Ngân sách</th>
                <th>Cập nhật</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/documentary/${p.id}`}>
                      <strong>{p.title}</strong>
                    </Link>{" "}
                    {p.is_demo && <Badge tone="warn">MẪU</Badge>}
                    <div className="doc-muted">{p.topic.slice(0, 110)}</div>
                  </td>
                  <td>
                    <Badge tone={stateTone(p.state)}>{STATE_LABELS[p.state] ?? p.state}</Badge>
                  </td>
                  <td>{p.budget_usd === null ? "—" : `$${p.budget_usd}`}</td>
                  <td className="doc-muted">{new Date(p.updated_at).toLocaleString("vi-VN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button className="btn doc-btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => void reload()}>
        Làm mới
      </button>
    </div>
  );
}
