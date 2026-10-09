import { config } from "../config/env";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "./client";

const B = "/documentary";
const P = (id: number) => `${B}/projects/${id}`;

// ---- workflow -------------------------------------------------------------
export type GateStatusName = "pending" | "approved" | "stale" | "rejected";

export interface GateStatus {
  gate: string;
  review_state: string;
  status: GateStatusName;
  approved_version: number | null;
  current_version: number;
}

export interface DocProject {
  id: number;
  title: string;
  topic: string;
  language: string;
  state: string;
  failed_from_state: string | null;
  error_message: string | null;
  budget_usd: number | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocProjectDetail extends DocProject {
  gates: GateStatus[];
  next_state: string | null;
  blockers: string[];
}

export interface Approval {
  id: number;
  gate: string;
  decision: "approved" | "rejected" | "revoked";
  artifact_version: number;
  note: string | null;
  created_at: string;
}

export interface ReviewIssue {
  code: string;
  message: string;
}

export interface Review {
  ok: boolean;
  issues: ReviewIssue[];
  warnings: ReviewIssue[];
}

export const listProjects = () => apiGet<DocProject[]>(`${B}/projects`);
export const createProject = (body: { title: string; topic: string; budget_usd?: number | null }) =>
  apiPost<DocProjectDetail>(`${B}/projects`, body);
export const createDemoProject = () => apiPost<DocProjectDetail>(`${B}/projects/demo`);
export const getProject = (id: number) => apiGet<DocProjectDetail>(P(id));
export const getApprovals = (id: number) => apiGet<Approval[]>(`${P(id)}/approvals`);
export const advanceProject = (id: number) => apiPost<DocProjectDetail>(`${P(id)}/advance`);
export const approveGate = (id: number, gate: string, note?: string) =>
  apiPost<DocProjectDetail>(`${P(id)}/approve`, { gate, note: note || null });
export const rejectGate = (id: number, gate: string, note?: string) =>
  apiPost<DocProjectDetail>(`${P(id)}/reject`, { gate, note: note || null });
export const rewindProject = (id: number, to_state: string, note?: string) =>
  apiPost<DocProjectDetail>(`${P(id)}/rewind`, { to_state, note: note || null });
export const failProject = (id: number, message: string) => apiPost<DocProjectDetail>(`${P(id)}/fail`, { message });
export const resumeProject = (id: number) => apiPost<DocProjectDetail>(`${P(id)}/resume`);

/** The review endpoint that backs each approval gate. */
export function getGateReview(id: number, gate: string): Promise<Review> {
  const path: Record<string, string> = {
    research: "research/review",
    script: "script/review",
    storyboard_assets: "assets/review",
    narration_timing: "timeline/review",
    final: "render/review",
  };
  const p = path[gate];
  if (!p) return Promise.resolve({ ok: true, issues: [], warnings: [] });
  return apiGet<Review>(`${P(id)}/${p}`).then((r) => ({ warnings: [], ...r }));
}

// ---- research -------------------------------------------------------------
export interface Source {
  id: number;
  project_id: number;
  title: string;
  url: string | null;
  publisher: string | null;
  author: string | null;
  published_date: string | null;
  accessed_date: string | null;
  excerpt: string | null;
  notes: string | null;
}
export type SourceInput = Omit<Source, "id" | "project_id">;

export type ClaimStatus = "verified" | "disputed" | "unverified";
export interface Claim {
  id: number;
  project_id: number;
  text: string;
  status: ClaimStatus;
  uncertainty_note: string | null;
  source_ids: number[];
}
export type ClaimInput = Pick<Claim, "text" | "status" | "uncertainty_note" | "source_ids">;

export const listSources = (id: number) => apiGet<Source[]>(`${P(id)}/sources`);
export const addSource = (id: number, b: SourceInput) => apiPost<Source>(`${P(id)}/sources`, b);
export const updateSource = (id: number, sid: number, b: SourceInput) => apiPut<Source>(`${P(id)}/sources/${sid}`, b);
export const deleteSource = (id: number, sid: number) => apiDelete<void>(`${P(id)}/sources/${sid}`);
export const listClaims = (id: number) => apiGet<Claim[]>(`${P(id)}/claims`);
export const addClaim = (id: number, b: ClaimInput) => apiPost<Claim>(`${P(id)}/claims`, b);
export const updateClaim = (id: number, cid: number, b: ClaimInput) => apiPut<Claim>(`${P(id)}/claims/${cid}`, b);
export const deleteClaim = (id: number, cid: number) => apiDelete<void>(`${P(id)}/claims/${cid}`);

// ---- script -----------------------------------------------------------------
export type SectionKind =
  | "hook"
  | "context"
  | "timeline"
  | "evidence"
  | "turning_point"
  | "consequences"
  | "conclusion";

export const SECTION_LABELS: Record<SectionKind, string> = {
  hook: "Mở đầu gây chú ý",
  context: "Bối cảnh lịch sử",
  timeline: "Dòng thời gian sự kiện",
  evidence: "Bằng chứng và các cách giải thích",
  turning_point: "Bước ngoặt",
  consequences: "Hệ quả",
  conclusion: "Kết luận và câu hỏi còn bỏ ngỏ",
};

export interface OutlineItem {
  kind: SectionKind;
  summary: string;
  claim_ids: number[];
}
export interface ScriptParagraph {
  text: string;
  factual: boolean;
  claim_ids: number[];
}
export interface ScriptSection {
  kind: SectionKind;
  heading: string;
  paragraphs: ScriptParagraph[];
}
export interface Script {
  version: number;
  origin: string;
  outline: OutlineItem[];
  sections: ScriptSection[];
  created_at: string;
  word_count: number;
  estimated_seconds: number;
  within_target: boolean;
  target_seconds: [number, number];
}

/** 404 = the project simply has no script yet. */
export const getScript = (id: number) =>
  apiGet<Script>(`${P(id)}/script`).catch((e: Error) => {
    if (/not found/i.test(e.message)) return null;
    throw e;
  });
export const getScriptHistory = (id: number) => apiGet<Script[]>(`${P(id)}/script/history`);
export const saveScript = (id: number, b: { outline: OutlineItem[]; sections: ScriptSection[] }) =>
  apiPut<Script>(`${P(id)}/script`, b);
export const generateOutline = (id: number, provider: "mock" | "llm") =>
  apiPost<Script>(`${P(id)}/script/outline`, { provider });
export const generateScript = (id: number, provider: "mock" | "llm") =>
  apiPost<Script>(`${P(id)}/script/generate`, { provider });
export const getScriptProviders = () => apiGet<{ script: string[] }>(`${B}/providers`);

// ---- storyboard & assets -------------------------------------------------------
export const PRESETS = [
  "NewspaperStack",
  "ArchivalPortrait",
  "MapZoom",
  "TimelineBuild",
  "BigNumber",
  "EvidenceBoard",
  "PhotoKenBurns",
  "HeadlineImpact",
  "SplitComparison",
] as const;

export type AssetState =
  | "programmatic"
  | "missing"
  | "pending"
  | "approved"
  | "rejected"
  | "stale"
  | "file_missing";

export interface OnScreenText {
  text: string;
  role: "headline" | "label" | "date" | "number" | "caption";
}
export interface Scene {
  id: number;
  scene_key: string;
  order_index: number;
  section_kind: SectionKind;
  narration_text: string;
  claim_ids: number[];
  visual_objective: string;
  visual_preset: string;
  asset_strategy: "programmatic" | "image";
  image_group: string | null;
  asset_id: number | null;
  asset_state: AssetState;
  on_screen_text: OnScreenText[];
  motion_notes: string | null;
  sfx_cues: string[];
  expected_duration: number;
  actual_duration: number | null;
  render_status: string;
  user_edited: boolean;
}
export interface SceneUpdate {
  visual_preset?: string;
  visual_objective?: string;
  on_screen_text?: OnScreenText[];
  motion_notes?: string;
  sfx_cues?: string[];
}
export interface Asset {
  id: number;
  project_id: number;
  path: string;
  type: string;
  origin: "imported" | "archival" | "ai_manual";
  source_url: string | null;
  license: string | null;
  attribution: string | null;
  prompt: string | null;
  model: string | null;
  input_hash: string | null;
  content_hash: string;
  width: number | null;
  height: number | null;
  tags: string[];
  approval_status: "pending" | "approved" | "rejected";
  created_at: string;
}

export const planStoryboard = (id: number) =>
  apiPost<{ scenes: number; created: number; kept: number; removed: number; image_groups: number; programmatic: number }>(
    `${P(id)}/storyboard/plan`,
  );
export const listScenes = (id: number) => apiGet<Scene[]>(`${P(id)}/scenes`);
export const updateScene = (id: number, sceneId: number, b: SceneUpdate) =>
  apiPut<Scene>(`${P(id)}/scenes/${sceneId}`, b);
export const listAssets = (id: number) => apiGet<Asset[]>(`${P(id)}/assets`);
export const importAsset = (
  id: number,
  b: { path: string; origin: "imported" | "archival"; license?: string; attribution?: string; source_url?: string },
) => apiPost<Asset>(`${P(id)}/assets/import`, b);
export const approveAsset = (id: number, aid: number) => apiPost<Asset>(`${P(id)}/assets/${aid}/approve`);
export const rejectAsset = (id: number, aid: number) => apiPost<Asset>(`${P(id)}/assets/${aid}/reject`);
export const patchAsset = (
  id: number,
  aid: number,
  b: { license?: string; attribution?: string; source_url?: string },
) => apiPatch<Asset>(`${P(id)}/assets/${aid}`, b);
export const assignAsset = (id: number, sceneId: number, assetId: number | null) =>
  apiPut<Scene[]>(`${P(id)}/scenes/${sceneId}/asset`, { asset_id: assetId });
export const exportImageCsv = (id: number) =>
  apiGet<{ to_generate: number; reused_from_cache: number; filename: string; csv: string }>(`${P(id)}/images/export-csv`);
export const importImageFolder = (id: number, folder: string) =>
  apiPost<{ imported: string[]; duplicate: string[]; unmatched: string[]; failed: { file: string; reason: string }[] }>(
    `${P(id)}/images/import-folder`,
    { folder },
  );
export const assetFileUrl = (id: number, aid: number) => `${config.apiBaseUrl}${P(id)}/assets/${aid}/file`;

// ---- narration & timeline -----------------------------------------------------------
export interface Segment {
  segment_key: string;
  order_index: number;
  text: string;
  scene_keys: string[];
  status: "pending" | "ready" | "failed";
  is_current: boolean;
  duration_sec: number | null;
  chars: number;
  provider: string | null;
  voice: string | null;
  cost_usd: number | null;
  has_word_stamps: boolean;
  attempts: number;
  error: string | null;
  master_start: number | null;
  master_end: number | null;
}
export interface Estimate {
  backend: string;
  paid: boolean;
  segments_total: number;
  segments_to_generate: number;
  segment_keys: string[];
  chars: number;
  estimated_cost_usd: number | null;
  spent_usd: number;
  spent_unknown_rows: number;
  budget_usd: number | null;
}
export interface GenerateResult {
  generated: string[];
  skipped_cached: number;
  failed: { segment: string; reason: string }[];
}
export interface SceneTiming {
  scene_key: string;
  order_index: number;
  start: number;
  end: number;
  duration: number;
  source: "tts_provider" | "whisper_local" | "estimated" | "manual";
  coverage: number;
  needs_review: boolean;
}
export interface Subtitle {
  order_index: number;
  start: number;
  end: number;
  text: string;
  scene_key: string | null;
  source: string;
}

export const getTtsBackends = () => apiGet<{ backends: string[] }>(`${B}/tts-backends`);
export const getAlignmentStatus = () => apiGet<{ whisper_installed: boolean; whisper_model: string }>(`${B}/alignment-status`);
export const planNarration = (id: number) =>
  apiPost<{ segments: number; created: number; kept: number; removed: number }>(`${P(id)}/narration/plan`);
export const listSegments = (id: number) => apiGet<Segment[]>(`${P(id)}/narration`);
export const estimateNarration = (id: number, backend: string) =>
  apiPost<Estimate>(`${P(id)}/narration/estimate`, { backend });
export const generateNarration = (id: number, backend: string, confirm: boolean, only?: string[]) =>
  apiPost<GenerateResult>(`${P(id)}/narration/generate`, { backend, confirm, only: only ?? null });
export const buildMaster = (id: number) =>
  apiPost<{ rebuilt: boolean; duration_sec: number; path: string }>(`${P(id)}/narration/master`);
export const masterAudioUrl = (id: number) => `${config.apiBaseUrl}${P(id)}/narration/master/audio`;
export const segmentAudioUrl = (id: number, key: string, v?: string | null) =>
  `${config.apiBaseUrl}${P(id)}/narration/${key}/audio${v ? `?v=${v}` : ""}`;
export const alignTimeline = (id: number, method: string, only?: string[]) =>
  apiPost<{ aligned: string[]; cached: number; details: { segment: string; source: string; coverage: number }[] }>(
    `${P(id)}/timeline/align`,
    { method, only: only ?? null },
  );
export const assembleTimeline = (id: number) =>
  apiPost<{ scenes: number; subtitles: number; errors: number; warnings: number }>(`${P(id)}/timeline/assemble`);
export const getTimeline = (id: number) => apiGet<SceneTiming[]>(`${P(id)}/timeline`);
export const getSubtitles = (id: number) => apiGet<Subtitle[]>(`${P(id)}/subtitles`);
export const setSceneStart = (id: number, sceneKey: string, start: number) =>
  apiPut(`${P(id)}/timeline/scenes/${sceneKey}/start`, { start });
export const clearSceneStart = (id: number, sceneKey: string) =>
  apiDelete(`${P(id)}/timeline/scenes/${sceneKey}/start`);
export const srtUrl = (id: number) => `${config.apiBaseUrl}${P(id)}/subtitles.srt`;
export const csvDownloadUrl = (id: number) => `${config.apiBaseUrl}${P(id)}/images/export-csv/download`;

// ---- render ------------------------------------------------------------------------------
export interface QcItem {
  code: string;
  message: string;
  scene?: string;
  start?: number;
  end?: number;
}
export interface RenderJob {
  id: number;
  kind: "preview" | "final";
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  phase: string | null;
  progress: number;
  params: { scale: number; seconds: number | null; burn_subtitles: boolean; grayscale: boolean; normalize_audio: boolean; theme?: "collage" | "cinematic" };
  error: string | null;
  duration_sec: number | null;
  qc: { ok: boolean; issues: QcItem[]; warnings: QcItem[]; width: number | null; height: number | null; has_audio: boolean; black_intervals: number } | null;
  has_output: boolean;
  created_at: string;
  finished_at: string | null;
  reused: boolean;
}
export interface RenderRequest {
  kind: "preview" | "final";
  scale?: number;
  seconds?: number | null;
  burn_subtitles?: boolean;
  normalize_audio?: boolean;
  theme?: "collage" | "cinematic";
}
export const renderPreflight = (id: number) => apiGet<Review>(`${P(id)}/render/preflight`);
export const renderTools = () => apiGet<Record<string, boolean>>(`${B}/render-tools`);
export const startRender = (id: number, b: RenderRequest) => apiPost<RenderJob>(`${P(id)}/render`, b);
export const listRenderJobs = (id: number) => apiGet<RenderJob[]>(`${P(id)}/render/jobs`);
export const cancelRender = (id: number, jobId: number) => apiPost<RenderJob>(`${P(id)}/render/jobs/${jobId}/cancel`);
export const renderLogUrl = (id: number, jobId: number) => `${config.apiBaseUrl}${P(id)}/render/jobs/${jobId}/log`;
export const renderVideoUrl = (id: number, jobId: number) => `${config.apiBaseUrl}${P(id)}/render/jobs/${jobId}/video`;

// ---- export --------------------------------------------------------------------------------
export interface ExportBundle {
  id: number;
  render_job_id: number;
  path: string;
  files: Record<string, { sha256: string; bytes: number }>;
  warnings: { code: string; message: string }[];
  created_at: string;
}
export const exportProject = (id: number) => apiPost<ExportBundle>(`${P(id)}/export`);
export const listExports = (id: number) => apiGet<ExportBundle[]>(`${P(id)}/exports`);
export const openExportFolder = (id: number, exportId: number) => apiPost<void>(`${P(id)}/exports/${exportId}/open-folder`);

// ---- ElevenLabs voice settings ---------------------------------------------------------
export interface ElevenLabsSettings {
  has_api_key: boolean;
  voice_id: string | null;
  model_id: string;
  stability: number;
  similarity_boost: number;
  style: number;
  speed: number;
  usd_per_1k_chars: number | null;
  ready: boolean;
}
export const getElevenLabsSettings = () =>
  apiGet<{ elevenlabs: ElevenLabsSettings }>("/settings").then((s) => s.elevenlabs);
export const saveElevenLabsSettings = (b: Partial<{
  api_key: string;
  voice_id: string;
  model_id: string;
  stability: number;
  similarity_boost: number;
  style: number;
  speed: number;
  usd_per_1k_chars: number;
}>) => apiPut<ElevenLabsSettings>("/settings/elevenlabs", b);

// ---- display helpers --------------------------------------------------------------------
export const PHASE_LABELS: Record<string, string> = {
  preparing: "Chuẩn bị dữ liệu",
  bundling: "Đóng gói Remotion",
  rendering: "Vẽ từng khung hình",
  muxing: "Ghép tiếng",
  validating: "Kiểm tra video",
  done: "Xong",
};

export const STATE_LABELS: Record<string, string> = {
  draft: "Nháp",
  research_review: "Duyệt nghiên cứu",
  script_review: "Duyệt kịch bản",
  storyboard_review: "Duyệt storyboard",
  asset_generation: "Chuẩn bị ảnh",
  asset_review: "Duyệt ảnh",
  audio_ready: "Narration & timing",
  render_preview: "Render preview",
  final_review: "Duyệt cuối",
  approved: "Đã duyệt",
  exported: "Đã xuất",
  failed: "Lỗi",
};

export const GATE_LABELS: Record<string, string> = {
  research: "Cổng 1 · Nghiên cứu & khẳng định",
  script: "Cổng 2 · Kịch bản",
  storyboard_assets: "Cổng 3 · Storyboard & ảnh",
  narration_timing: "Cổng 4 · Narration & timing",
  final: "Cổng 5 · Video cuối",
};

export function fmtTime(sec: number | null | undefined): string {
  if (sec === null || sec === undefined) return "—";
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}
