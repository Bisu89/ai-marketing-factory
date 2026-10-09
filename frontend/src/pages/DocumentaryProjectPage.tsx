import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { getProject, GATE_LABELS, STATE_LABELS } from "../api/documentary";
import { Badge, Loading, Notice, useLoader } from "./documentary/shared";
import { OverviewTab } from "./documentary/OverviewTab";
import { ResearchTab } from "./documentary/ResearchTab";
import { ScriptTab } from "./documentary/ScriptTab";
import { StoryboardTab } from "./documentary/StoryboardTab";
import { AssetsTab } from "./documentary/AssetsTab";
import { NarrationTab } from "./documentary/NarrationTab";
import { RenderTab } from "./documentary/RenderTab";
import { VoiceSettingsTab } from "./documentary/VoiceSettingsTab";
import "./documentary/documentary.css";

const TABS = [
  { id: "overview", label: "Tổng quan" },
  { id: "research", label: "Nghiên cứu" },
  { id: "script", label: "Kịch bản" },
  { id: "storyboard", label: "Storyboard" },
  { id: "assets", label: "Ảnh" },
  { id: "narration", label: "Giọng đọc & Timeline" },
  { id: "render", label: "Render" },
  { id: "voice", label: "Cài đặt giọng" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function DocumentaryProjectPage() {
  const id = Number(useParams().id);
  const [tab, setTab] = useState<TabId>("overview");
  const { data: project, error, loading, reload } = useLoader(() => getProject(id), id);

  if (!Number.isFinite(id)) return <Notice kind="error">Mã dự án không hợp lệ.</Notice>;
  if (loading && !project) return <Loading />;
  if (error && !project) {
    return (
      <div className="doc-page">
        <Notice kind="error">{error}</Notice>
        <Link to="/documentary">← Về danh sách</Link>
      </div>
    );
  }
  if (!project) return null;

  const reloadProject = () => void reload();
  const props = { project, reloadProject };

  return (
    <div className="doc-page">
      <PageHeader
        title={project.title}
        subtitle={project.topic.slice(0, 160)}
        actions={
          <>
            {project.is_demo && <Badge tone="warn">DỰ ÁN MẪU — không phải lịch sử đã kiểm chứng</Badge>}
            <Badge tone={project.state === "failed" ? "bad" : "info"}>{STATE_LABELS[project.state] ?? project.state}</Badge>
            <Link className="btn btn-sm" to="/documentary">
              <ArrowLeft size={14} /> Danh sách
            </Link>
          </>
        }
      />

      <div className="doc-stepper" aria-label="Các cổng duyệt">
        {project.gates.map((g) => (
          <span
            key={g.gate}
            className={`doc-step${g.status === "approved" ? " done" : ""}${g.review_state === project.state ? " current" : ""}`}
            title={`v${g.current_version}${g.status === "stale" ? " — duyệt đã cũ" : ""}`}
          >
            {g.status === "approved" && <Check size={13} />}
            {GATE_LABELS[g.gate]}
            {g.status === "stale" && <Badge tone="warn">cũ</Badge>}
          </span>
        ))}
      </div>

      <div className="doc-tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={`doc-tab${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab key={project.id} {...props} />}
      {tab === "research" && <ResearchTab key={project.id} {...props} />}
      {tab === "script" && <ScriptTab key={project.id} {...props} />}
      {tab === "storyboard" && <StoryboardTab key={project.id} {...props} />}
      {tab === "assets" && <AssetsTab key={project.id} {...props} />}
      {tab === "narration" && <NarrationTab key={project.id} {...props} />}
      {tab === "render" && <RenderTab key={project.id} {...props} />}
      {tab === "voice" && <VoiceSettingsTab />}
    </div>
  );
}
