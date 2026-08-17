import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Ban,
  Check,
  CheckCircle2,
  Circle,
  Clapperboard,
  FilePlus2,
  Film,
  FolderOpen,
  Image as ImageIcon,
  Loader2,
  Music,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  Wand2,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { ProductionProgress } from "../components/ProductionProgress";
import { EmptyState } from "../components/EmptyState";
import { AssetBrowserModal } from "../components/AssetBrowserModal";
import { assetFileUrl, getAsset } from "../api/asset";
import { generateBeatPlan, getProject, loadBeatPlan, renderBeatPreview, saveBeatPlan, saveProjectBeatPlan } from "../api/beat";
import { checkPlanQuality } from "../api/quality";
import { createTemplate, listTemplates } from "../api/template";
import { listLocalVoices } from "../api/voice";
import type { LocalVoiceOption } from "../api/voice";
import {
  cancelVideoComposeJob,
  getVideoComposeJob,
  listVideoComposeJobs,
  openVideoComposeJobFolder,
  retryVideoComposeJob,
} from "../api/videoComposer";
import { renderComposition } from "../api/videoFactory";
import { mediaUrl } from "../api/client";
import type { Asset } from "../types/asset";
import type { RenderPhase, VideoComposeJob } from "../types/videoComposer";
import { DIMENSION_LABELS } from "../types/quality";
import type { QualityReport } from "../types/quality";
import {
  BEAT_MOTION_PRESET_DESCRIPTIONS,
  BEAT_MOTION_PRESET_LABELS,
  BEAT_MOTION_PRESETS,
  BEAT_TYPES,
  CAPTION_PRESETS,
  CAPTION_PRESET_LABELS,
  MOTION_PRESET_DEFAULTS,
  SYSTEM_DEFAULT_PROJECT_CONFIG,
  effectiveMotionPreset,
} from "../types/videoFactory";
import type {
  BeatMotionPreset,
  BeatPreviewResult,
  BeatType,
  CaptionPreset,
  ContentBrief,
  GeneratedBeat,
  GeneratedBeatPlan,
  MotionPresetName,
  OutputFormat,
  ProjectConfig,
  Scene,
  Template,
  VoiceProjectConfig,
  WorkingBeat,
} from "../types/videoFactory";
import type { CompositionPlan } from "../types/videoFactory";
import "./VideoFactoryPage.css";

const VOICE_OPTIONS: { value: string; label: string }[] = [
  { value: "en-US-GuyNeural", label: "English (Male)" },
  { value: "en-US-AriaNeural", label: "English (Female)" },
  { value: "es-ES-AlvaroNeural", label: "Spanish (Male)" },
  { value: "es-ES-ElviraNeural", label: "Spanish (Female)" },
  { value: "vi-VN-NamMinhNeural", label: "Vietnamese (Male)" },
  { value: "vi-VN-HoaiMyNeural", label: "Vietnamese (Female)" },
];

const OUTPUT_FORMAT: OutputFormat = { width: 1080, height: 1920, fps: 30 };
// OUTPUT_FORMAT is a fixed 1080x1920 constant (see types/videoFactory.ts's
// buildScene) -- always vertical, so the aspect-ratio badge in the header
// can just be a fixed label rather than computed from a GCD reduction.
const ASPECT_RATIO_LABEL = "9:16";
const POLL_INTERVAL_MS = 2000;

const STATUS_LABEL: Record<VideoComposeJob["status"], string> = {
  queued: "Queued",
  rendering_beats: "Rendering beats",
  merging: "Composing video",
  narrating: "Generating narration",
  subtitling: "Generating captions",
  mixing_audio: "Building audio",
  finalizing: "Burning captions",
  validating: "Validating output",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};
const IN_PROGRESS_STATUSES: VideoComposeJob["status"][] = [
  "queued",
  "rendering_beats",
  "merging",
  "narrating",
  "subtitling",
  "mixing_audio",
  "finalizing",
  "validating",
];

// Task 11 -- see docs/features/38-render-job-hardening.md. Drives the
// "Preparing / Rendering Beat X/Y / Composing / Building Audio / Burning
// Captions / Validating" checklist -- only phases the backend actually
// reports (job.phase, job.progress_current/total) are ever shown; nothing
// here is a guessed/interpolated percentage.
const PHASE_ORDER: { phase: RenderPhase; label: string }[] = [
  { phase: "RENDER_BEATS", label: "Rendering beats" },
  { phase: "COMPOSE_VIDEO", label: "Composing video" },
  { phase: "BUILD_AUDIO", label: "Building audio" },
  { phase: "BURN_CAPTIONS", label: "Burning captions" },
  { phase: "VALIDATE_OUTPUT", label: "Validating output" },
];

type Step = 1 | 2 | 3 | 4 | 5;

const STEPS: { id: Step; label: string }[] = [
  { id: 1, label: "Script" },
  { id: 2, label: "Beats" },
  { id: 3, label: "Visuals" },
  { id: 4, label: "Audio" },
  { id: 5, label: "Render" },
];

let beatIdCounter = 0;
function nextBeatId(): string {
  beatIdCounter += 1;
  return `beat_${beatIdCounter}_${Date.now()}`;
}

function makeBeat(overrides: Partial<WorkingBeat> = {}): WorkingBeat {
  return {
    id: nextBeatId(),
    order: 1,
    type: "BODY",
    narration: "",
    duration: 3,
    visualHint: null,
    // null = inherit the project's default motion (Task 12) -- a brand
    // new beat hasn't had an explicit choice made for it yet.
    motionPreset: null,
    assetPath: "",
    assetId: null,
    assetStatus: "unregistered",
    assetError: null,
    narrationAssetPath: "",
    narrationAssetId: null,
    narrationAssetStatus: "unregistered",
    narrationAssetError: null,
    ...overrides,
  };
}

// Beats coming from the backend (generated or loaded from beats.json)
// already have a real, stable id -- reuse it instead of minting a new one,
// so a save-then-reload round trip doesn't silently change ids on every
// beat. "Add beat manually" is the only case that goes through makeBeat()
// without an id override, since it has no backend-assigned id to reuse.
function workingBeatFromDTO(beat: GeneratedBeat): WorkingBeat {
  return makeBeat({
    id: beat.id,
    order: beat.order,
    type: beat.type,
    narration: beat.narration ?? "",
    duration: beat.duration,
    visualHint: beat.visual_hint,
    motionPreset: beat.motion_preset,
    assetId: beat.asset_id,
    // assetPath is intentionally left blank here -- beats.json only stores
    // the bare asset_id (see backend/app/modules/beat/schemas.py's module
    // docstring), never a copied path. resolveAssetReferences() below
    // re-resolves id -> path/availability against the Asset library right
    // after load, which is also where a broken/deleted reference surfaces.
    assetStatus: beat.asset_id != null ? "registered" : "unregistered",
    narrationAssetId: beat.narration_asset_id,
    narrationAssetStatus: beat.narration_asset_id != null ? "registered" : "unregistered",
  });
}

function toBeatDTO(beat: WorkingBeat, order: number): GeneratedBeat {
  return {
    id: beat.id,
    order,
    type: beat.type,
    // Beat.narration/visual_hint reject whitespace-only strings if provided
    // (see backend/app/modules/beat/schemas.py) -- normalize an empty/blank
    // field to null here rather than duplicating that rule client-side.
    narration: beat.narration.trim() ? beat.narration : null,
    duration: beat.duration,
    visual_hint: beat.visualHint && beat.visualHint.trim() ? beat.visualHint : null,
    asset_id: beat.assetId,
    motion_preset: beat.motionPreset,
    narration_asset_id: beat.narrationAssetId,
  };
}

// Re-resolves every beat's bare asset_id/narration_asset_id against the
// Asset library right after loading a saved BeatPlan: beats.json only
// stores ids, never a path, and a referenced asset may have been deleted,
// moved to a different type, or never existed (a hand-edited file) since
// it was saved. Runs once per load rather than lazily per-selection, so
// every beat's list-item badges and detail-panel previews are already
// accurate without a second fetch when the user selects one.
async function resolveAssetReferences(beats: WorkingBeat[]): Promise<WorkingBeat[]> {
  const visualIds = new Set(beats.filter((b) => b.assetId != null).map((b) => b.assetId as number));
  const narrationIds = new Set(beats.filter((b) => b.narrationAssetId != null).map((b) => b.narrationAssetId as number));
  const idsToResolve = Array.from(new Set([...visualIds, ...narrationIds]));
  if (idsToResolve.length === 0) return beats;

  const resolved = new Map<number, Asset | null>();
  await Promise.all(
    idsToResolve.map(async (id) => {
      try {
        resolved.set(id, await getAsset(id));
      } catch {
        resolved.set(id, null);
      }
    })
  );

  return beats.map((beat) => {
    let next = beat;
    if (beat.assetId != null) {
      const asset = resolved.get(beat.assetId);
      next =
        asset && asset.type === "image"
          ? { ...next, assetPath: asset.path, assetStatus: "registered", assetError: null }
          : { ...next, assetStatus: "error", assetError: "The selected image is no longer available in the Library." };
    }
    if (beat.narrationAssetId != null) {
      const asset = resolved.get(beat.narrationAssetId);
      next =
        asset && asset.type === "audio"
          ? { ...next, narrationAssetPath: asset.path, narrationAssetStatus: "registered", narrationAssetError: null }
          : {
              ...next,
              narrationAssetStatus: "error",
              narrationAssetError: "The selected audio is no longer available in the Library.",
            };
    }
    return next;
  });
}

function buildBeatPlanForSave(
  beats: WorkingBeat[],
  script: string,
  projectName: string,
  config: ProjectConfig,
  // Task 21 -- preserved as-loaded (this page has no UI to edit them),
  // never silently dropped on save. scriptLocked additionally auto-locks
  // the instant the script text actually differs from what was loaded --
  // "human edits always win" (section 17) shouldn't require a separate,
  // not-yet-built lock toggle to take effect for the one real editing
  // surface this page already has.
  idea: string | null,
  contentBrief: ContentBrief | null,
  scriptLocked: boolean,
  loadedScriptText: string | null
): GeneratedBeatPlan {
  // `order` is always derived from the beats array's current position, not
  // from any per-beat field kept in sync separately -- there is no other
  // source of truth for order, so it can never drift.
  const dtoBeats = beats.map((beat, index) => toBeatDTO(beat, index + 1));
  const scriptChanged = script.trim() !== (loadedScriptText ?? "").trim();
  return {
    video_id: null,
    script_text: script.trim() ? script : null,
    beats: dtoBeats,
    total_duration: dtoBeats.reduce((sum, beat) => sum + beat.duration, 0),
    project_name: projectName.trim() ? projectName : null,
    config,
    idea,
    content_brief: contentBrief,
    script_locked: scriptLocked || scriptChanged,
  };
}

function filenameFromPath(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

interface AudioCaptionSettings {
  voice: string;
  narrationVolume: number;
  musicPath: string;
  musicVolume: number;
  duckingRatio: number;
  fadeIn: number;
  fadeOut: number;
  captionPreset: CaptionPreset;
}

function buildScene(beat: WorkingBeat, order: number, captionPreset: CaptionPreset, projectConfig: ProjectConfig): Scene {
  // WorkingBeat.motionPreset is one of the 6 uppercase BeatMotionPreset
  // values (the persisted Beat-level contract) or null ("inherit the
  // project default" -- Task 12, resolved via effectiveMotionPreset here,
  // the same "Beat override > Project default > System default" resolver
  // the backend uses). MOTION_PRESET_DEFAULTS is keyed by the 9 lowercase
  // MotionPresetName values this app's renderer understands. All 6 share a
  // spelling with a MotionPresetName member, so lowercasing is a safe,
  // total lookup, not a partial/fallback mapping.
  const resolvedPreset = effectiveMotionPreset(beat.motionPreset, projectConfig);
  const renderPresetName = resolvedPreset.toLowerCase() as MotionPresetName;
  const motionDefaults = MOTION_PRESET_DEFAULTS[renderPresetName];
  return {
    id: beat.id,
    order,
    beat_id: beat.id,
    duration: beat.duration,
    source_asset_id: beat.assetId as number,
    motion: {
      preset_name: renderPresetName,
      scale: motionDefaults.scale,
      position: motionDefaults.position,
      rotation: motionDefaults.rotation,
      easing: "ease_in_out",
    },
    caption: { text: beat.narration, preset: captionPreset },
    audio: { sfx: null, sfx_volume: 1.0, narration_asset_id: beat.narrationAssetId },
    transition: { type: "crossfade", duration: 0.4 },
    output_format: OUTPUT_FORMAT,
  };
}

function buildCompositionPlan(
  beats: WorkingBeat[],
  settings: AudioCaptionSettings,
  projectConfig: ProjectConfig
): { plan: CompositionPlan; assetPaths: Record<number, string>; narrationAssetPaths: Record<number, string> } {
  const scenes = beats.map((beat, index) => buildScene(beat, index + 1, settings.captionPreset, projectConfig));
  const assetPaths: Record<number, string> = {};
  const narrationAssetPaths: Record<number, string> = {};
  beats.forEach((beat) => {
    if (beat.assetId != null) assetPaths[beat.assetId] = beat.assetPath.trim();
    if (beat.narrationAssetId != null) narrationAssetPaths[beat.narrationAssetId] = beat.narrationAssetPath.trim();
  });

  const plan: CompositionPlan = {
    video_id: null,
    narration_script: beats.map((beat) => beat.narration).join(" "),
    voice: settings.voice,
    language: null,
    narration_volume: settings.narrationVolume,
    music_path: settings.musicPath.trim() ? settings.musicPath.trim() : null,
    music_volume: settings.musicVolume,
    music_ducking_ratio: settings.duckingRatio,
    fade_in_sec: settings.fadeIn,
    fade_out_sec: settings.fadeOut,
    caption_preset: settings.captionPreset,
    scenes,
  };
  return { plan, assetPaths, narrationAssetPaths };
}

function validatePlan(beats: WorkingBeat[], script: string): string[] {
  const errors: string[] = [];
  if (!script.trim() && beats.length === 0) {
    errors.push("Enter a script and generate beats, or add a beat manually.");
  }
  if (beats.length === 0) {
    errors.push("At least one beat is required.");
  }
  beats.forEach((beat, index) => {
    const label = `Beat ${index + 1}`;
    if (!beat.narration.trim()) errors.push(`${label}: narration text is empty.`);
    if (beat.duration <= 0) errors.push(`${label}: duration must be greater than 0.`);
    if (beat.assetId == null) errors.push(`${label}: no asset assigned -- choose an image in the Visuals step.`);
  });
  return errors;
}

export function VideoFactoryPage() {
  // Task 13 -- opened as /video-factory?project=<id>[&batch=<batchId>] when
  // editing one project out of a batch (see docs/features/40-batch-video-creation.md
  // and BatchDetailPage.tsx's "Open Project" links) instead of this app's
  // one singleton beats.json draft. `batch`, when present, is only used to
  // render a "back to batch" link -- it plays no role in loading/saving.
  const [searchParams] = useSearchParams();
  const projectIdParam = searchParams.get("project");
  const projectId = projectIdParam ? Number(projectIdParam) : null;
  const batchIdParam = searchParams.get("batch");

  const [step, setStep] = useState<Step>(1);
  const [script, setScript] = useState("");
  // Task 21 -- see docs/features/47-content-brief-script-engine.md. This
  // page has no UI to edit idea/content_brief yet -- these three exist
  // purely so a Save here never silently wipes them (the same
  // preserve-on-save shape buildProjectConfigForSave already uses for
  // ProjectConfig.factory). loadedScriptText is what backs "did the user
  // actually change the script" -> auto-lock on save (section 17: "human
  // edits always win").
  const [idea, setIdea] = useState<string | null>(null);
  const [contentBrief, setContentBrief] = useState<ContentBrief | null>(null);
  const [scriptLocked, setScriptLocked] = useState(false);
  const [loadedScriptText, setLoadedScriptText] = useState<string | null>(null);
  const [beats, setBeats] = useState<WorkingBeat[]>([]);
  const [selectedBeatId, setSelectedBeatId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [projectDataLoaded, setProjectDataLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Task 12 -- see docs/features/39-project-templates.md. This app has no
  // multi-project store (only one BeatPlan is ever "the" current one --
  // see app/modules/beat/router.py's own module docstring); projectConfig
  // is that one project's render/motion/caption/audio configuration,
  // snapshotted from whichever Template the user picked (or plain system
  // defaults for an existing, template-less project).
  const [projectName, setProjectName] = useState("");
  const [projectConfig, setProjectConfig] = useState<ProjectConfig>(SYSTEM_DEFAULT_PROJECT_CONFIG);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [saveTemplateName, setSaveTemplateName] = useState("");
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [saveTemplateError, setSaveTemplateError] = useState<string | null>(null);

  const [title, setTitle] = useState("Video Factory Composition");
  const [voice, setVoice] = useState(VOICE_OPTIONS[0].value);
  const [narrationVolume, setNarrationVolume] = useState(1.0);
  const [musicPath, setMusicPath] = useState("");
  // Only set when musicPath came from the Asset Browser -- lets the
  // preview player resolve a URL via assetFileUrl(). A manually-typed
  // path isn't necessarily a registered asset, so it has no id to preview
  // with (the render step still works either way; music_path is sent to
  // the backend as a plain path regardless of how it was chosen).
  const [musicAssetId, setMusicAssetId] = useState<number | null>(null);
  const [musicBrowserOpen, setMusicBrowserOpen] = useState(false);
  const [musicVolume, setMusicVolume] = useState(0.15);
  const [duckingRatio, setDuckingRatio] = useState(8.0);
  const [fadeIn, setFadeIn] = useState(0.0);
  const [fadeOut, setFadeOut] = useState(0.0);
  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>("emotional");
  const [outputDir, setOutputDir] = useState("");

  // Task 22 -- see docs/features/48-voice-factory-local-tts.md. "local"
  // (genuinely offline SAPI5) is this app's own default; edge_tts stays an
  // explicit opt-in, never auto-selected.
  const [voiceProvider, setVoiceProvider] = useState<VoiceProjectConfig["provider"]>("local");
  const [voiceId, setVoiceId] = useState("default");
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);
  const [localVoices, setLocalVoices] = useState<LocalVoiceOption[]>([]);
  const [localVoicesError, setLocalVoicesError] = useState<string | null>(null);

  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<VideoComposeJob | null>(null);
  const [openFolderError, setOpenFolderError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<VideoComposeJob[]>([]);

  // Task 16 -- Production Check (see docs/features/42-content-quality-gate.md).
  // qualityReport is only ever non-null while the modal is showing a
  // NEEDS_REVIEW/BLOCKED result -- a READY check never opens it at all.
  const [qualityChecking, setQualityChecking] = useState(false);
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null);
  const [qualityCheckOpen, setQualityCheckOpen] = useState(false);
  const [qualityCheckError, setQualityCheckError] = useState<string | null>(null);

  async function refreshRecentJobs() {
    try {
      const jobs = await listVideoComposeJobs();
      setRecentJobs(jobs.slice(0, 5));
    } catch {
      // Recent-renders list is a convenience, not load-bearing -- a
      // transient fetch failure here shouldn't surface as a page error.
    }
  }

  useEffect(() => {
    if (step === 5) refreshRecentJobs();
  }, [step, job?.status]);

  async function refreshTemplates() {
    try {
      setTemplatesError(null);
      setTemplates(await listTemplates());
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : "Could not load templates.");
    }
  }

  useEffect(() => {
    refreshTemplates();
  }, []);

  // Task 22 -- see docs/features/48-voice-factory-local-tts.md section 45.
  // Real, installed SAPI5 voices for the picker below -- fetched once
  // (what's installed doesn't change mid-session); a fetch failure just
  // leaves the picker on the plain "System Default" fallback rather than
  // blocking the page.
  useEffect(() => {
    (async () => {
      try {
        setLocalVoices(await listLocalVoices());
      } catch (err) {
        setLocalVoicesError(err instanceof Error ? err.message : "Could not load local voices.");
      }
    })();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Task 13 -- a batch project always already has its own config
        // (snapshotted from a Template at batch-creation time) and is a
        // real, already-existing row the moment it can be opened here, so
        // it never goes through the "nothing saved yet -> open the
        // template picker" branch below (that's specifically the
        // singleton-beats.json "New Video" entry point).
        const plan = projectId != null ? await getProject(projectId) : await loadBeatPlan();
        if (cancelled) return;
        if (!plan) {
          // Nothing saved yet -- a genuinely fresh session (Task 12's
          // "New Video" entry point). Existing projects (a real saved
          // plan, with or without a `config`) are never interrupted by
          // this -- see docs/features/39-project-templates.md section 15.
          setTemplatePickerOpen(true);
          return;
        }
        const loaded = plan.beats.map(workingBeatFromDTO);
        const resolved = await resolveAssetReferences(loaded);
        if (cancelled) return;
        setScript(plan.script_text ?? "");
        setLoadedScriptText(plan.script_text ?? "");
        setIdea(plan.idea ?? null);
        setContentBrief(plan.content_brief ?? null);
        setScriptLocked(plan.script_locked ?? false);
        setBeats(resolved);
        setSelectedBeatId(resolved[0]?.id ?? null);
        setProjectName(plan.project_name ?? "");
        // A pre-Task-12 saved plan has no `config` at all -- system
        // defaults (SYSTEM_DEFAULT_PROJECT_CONFIG's own initial state)
        // apply with zero migration, matching the backend's own default.
        if (plan.config) {
          setProjectConfig(plan.config);
          setCaptionPreset(plan.config.captions.preset);
          setMusicVolume(plan.config.audio.music_volume);
          if (plan.config.voice) {
            setVoiceProvider(plan.config.voice.provider);
            setVoiceId(plan.config.voice.voice_id);
            setVoiceSpeed(plan.config.voice.speed);
          }
        }
        setStep(2);
        setDirty(false);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Could not load saved beat plan.");
      } finally {
        // Task 18 -- see docs/features/44-one-click-factory-pipeline.md.
        // ProductionProgress's own render-job-ready handoff (setJobId +
        // setStep(5)) must never race ahead of this effect: it fetches the
        // FactoryRun independently and can resolve before this project
        // load does, which would otherwise land Step 5 on this page's
        // still-empty initial `beats` state (0 beats, 0 duration) instead
        // of the real, just-loaded project.
        if (!cancelled) setProjectDataLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (jobId == null) return;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | null = null;

    async function poll() {
      try {
        const data = await getVideoComposeJob(jobId as number);
        if (cancelled) return;
        setJob(data);
        // Stop polling once the job reaches a terminal state (Task 11 --
        // see docs/features/38-render-job-hardening.md) -- nothing more
        // will ever change for it.
        if (!IN_PROGRESS_STATUSES.includes(data.status) && interval != null) {
          clearInterval(interval);
          interval = null;
        }
      } catch {
        // Ignore a transient polling error; try again on the next tick.
      }
    }

    poll();
    interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (interval != null) clearInterval(interval);
    };
  }, [jobId]);

  function goToStep(target: Step) {
    setStep(target);
  }

  async function handleGenerateBeats() {
    if (!script.trim() || generating) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const result = await generateBeatPlan(script);
      const generated = result.beats.map(workingBeatFromDTO);
      setBeats(generated);
      setSelectedBeatId(generated[0]?.id ?? null);
      setValidationErrors([]);
      setDirty(true);
      setStep(2);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Could not generate beats.");
    } finally {
      setGenerating(false);
    }
  }

  function updateBeat(id: string, patch: Partial<WorkingBeat>) {
    setBeats((prev) => prev.map((beat) => (beat.id === id ? { ...beat, ...patch } : beat)));
    setDirty(true);
  }

  function removeBeat(id: string) {
    setBeats((prev) => {
      const index = prev.findIndex((beat) => beat.id === id);
      const next = prev.filter((beat) => beat.id !== id);
      if (selectedBeatId === id) {
        // Select the beat that ends up at the same position (the one that
        // was "next"), or the new last beat if the deleted one was last.
        const fallback = next[Math.min(index, next.length - 1)];
        setSelectedBeatId(fallback ? fallback.id : null);
      }
      return next;
    });
    setDirty(true);
  }

  function moveBeat(id: string, direction: -1 | 1) {
    setBeats((prev) => {
      const index = prev.findIndex((beat) => beat.id === id);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    setDirty(true);
  }

  function addBeatManually() {
    const beat = makeBeat({ order: beats.length + 1 });
    setBeats((prev) => [...prev, beat]);
    setSelectedBeatId(beat.id);
    setDirty(true);
  }

  // The one place that assembles ProjectConfig from current session state
  // (Task 12's "one deterministic configuration resolver... not spread
  // across UI components" -- see docs/features/39-project-templates.md).
  // projectConfig.render/motion/template_id/template_version only ever
  // change via "Use Template" (setProjectConfig); captions/audio are
  // derived fresh here from the existing flat controls (Step 4) every
  // time, so they're always in sync with what's actually on screen.
  function buildProjectConfigForSave(): ProjectConfig {
    return {
      render: projectConfig.render,
      motion: projectConfig.motion,
      captions: { enabled: true, preset: captionPreset },
      audio: {
        narration_enabled:
          beats.some((b) => b.narrationAssetId != null) || beats.some((b) => b.narration.trim().length > 0),
        music_enabled: musicPath.trim().length > 0,
        music_volume: musicVolume,
        ducking: duckingRatio > 1,
      },
      // Not sourced from any Step 4 control (this page has no factory-policy
      // UI) -- preserved as-loaded so saving here never silently resets a
      // project's own auto-assign/review policy back to defaults.
      factory: projectConfig.factory,
      // Same reasoning (Task 21) -- no content-profile UI on this page.
      content: projectConfig.content,
      // Task 22 -- see docs/features/48-voice-factory-local-tts.md. Sourced
      // from the Voice section below (Step 4), same shape as
      // captions/audio's own "derived fresh from on-screen controls" above.
      voice: {
        provider: voiceProvider,
        voice_id: voiceId,
        language: projectConfig.voice.language,
        speed: voiceSpeed,
        pitch: projectConfig.voice.pitch,
      },
      template_id: projectConfig.template_id,
      template_version: projectConfig.template_version,
    };
  }

  async function handleSaveBeatPlan() {
    if (beats.length === 0 || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const plan = buildBeatPlanForSave(
        beats, script, projectName, buildProjectConfigForSave(), idea, contentBrief, scriptLocked, loadedScriptText
      );
      if (projectId != null) {
        await saveProjectBeatPlan(projectId, plan);
      } else {
        await saveBeatPlan(plan);
      }
      setScriptLocked(plan.script_locked ?? false);
      setLoadedScriptText(plan.script_text ?? "");
      setDirty(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save beat plan.");
    } finally {
      setSaving(false);
    }
  }

  // Task 16 (see docs/features/42-content-quality-gate.md, sections 29/33):
  // runs the Quality Gate before every render submission. A READY result
  // proceeds straight through (no interruption -- the report is only
  // actionable feedback, not friction when everything's already fine).
  // NEEDS_REVIEW/BLOCKED opens the Production Check modal and stops here;
  // the modal's own "Render Anyway" button (NEEDS_REVIEW only -- BLOCKED
  // has no such button, matching acceptance criterion #15) re-calls this
  // function with bypassQualityCheck=true.
  async function handleSubmitRender(bypassQualityCheck = false) {
    const errors = validatePlan(beats, script);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    if (!bypassQualityCheck) {
      setQualityChecking(true);
      setQualityCheckError(null);
      try {
        const planForCheck = buildBeatPlanForSave(
          beats, script, projectName, buildProjectConfigForSave(), idea, contentBrief, scriptLocked, loadedScriptText
        );
        const report = await checkPlanQuality(planForCheck);
        setQualityReport(report);
        if (report.status !== "READY") {
          setQualityCheckOpen(true);
          return;
        }
      } catch (err) {
        // The check itself failing (e.g. a transient network hiccup)
        // shouldn't block rendering outright -- the existing render-time
        // preflight is still the real safety net underneath this, exactly
        // as it was before this task.
        setQualityCheckError(err instanceof Error ? err.message : "Could not run the production check.");
      } finally {
        setQualityChecking(false);
      }
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const { plan, assetPaths, narrationAssetPaths } = buildCompositionPlan(
        beats,
        {
          voice,
          narrationVolume,
          musicPath,
          // A template with audio.ducking=false means "no ducking" --
          // ffmpeg's own sidechaincompress ratio=1.0 is the real "no
          // effect" value (see backend's _mix_audio docstring), not a
          // separate on/off flag video_composer would need to understand.
          musicVolume,
          duckingRatio: projectConfig.audio.ducking ? duckingRatio : 1.0,
          fadeIn,
          fadeOut,
          captionPreset,
        },
        projectConfig
      );
      const result = await renderComposition({
        plan,
        asset_paths: assetPaths,
        title: title.trim() || "Video Factory Composition",
        output_dir: outputDir.trim() || undefined,
        narration_asset_paths: Object.keys(narrationAssetPaths).length > 0 ? narrationAssetPaths : undefined,
        profile: projectConfig.render.profile,
      });
      setJob(result);
      setJobId(result.id);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not start render.");
    } finally {
      setSubmitting(false);
    }
  }

  // "Quick Render" (Task 12 section 24): current project -> preflight ->
  // render, using the SAME renderComposition()/RenderJob/queue path as a
  // normal render -- no separate pipeline, no skipped validation. Only a
  // UX shortcut: jump straight to Render and submit, instead of clicking
  // through Steps 2-5 by hand.
  async function handleQuickRender() {
    setStep(5);
    await handleSubmitRender();
  }

  // Template -> ProjectConfig (Task 12 section 9): the project receives a
  // full, independent snapshot of the template's config -- template.config
  // is never held onto/referenced afterward, so nothing the user does next
  // can reach back and mutate the template itself (built-in or custom).
  function handleUseTemplate(template: Template) {
    const snapshot: ProjectConfig = JSON.parse(JSON.stringify(template.config));
    setProjectConfig(snapshot);
    setCaptionPreset(snapshot.captions.preset);
    setMusicVolume(snapshot.audio.music_volume);
    if (snapshot.voice) {
      setVoiceProvider(snapshot.voice.provider);
      setVoiceId(snapshot.voice.voice_id);
      setVoiceSpeed(snapshot.voice.speed);
    }
    setTemplatePickerOpen(false);
    setStep(1);
  }

  function handleOpenNewVideo() {
    if (beats.length > 0 || script.trim()) {
      const confirmed = window.confirm(
        "Starting a new video replaces your current draft (this app keeps only one project at a time). Continue?"
      );
      if (!confirmed) return;
      setBeats([]);
      setScript("");
      setSelectedBeatId(null);
      setProjectName("");
      setDirty(false);
    }
    setTemplatePickerOpen(true);
  }

  async function handleSaveAsTemplate() {
    if (!saveTemplateName.trim() || savingTemplate) return;
    setSavingTemplate(true);
    setSaveTemplateError(null);
    try {
      // sanitize_project_config_for_template on the backend strips template
      // provenance -- the frontend just sends the current, resolved
      // ProjectConfig as-is; it never contains asset/beat/job IDs (see
      // ProjectConfig's own schema) so there is nothing else to strip.
      await createTemplate({ name: saveTemplateName.trim(), config: buildProjectConfigForSave() });
      setSaveTemplateOpen(false);
      setSaveTemplateName("");
      await refreshTemplates();
    } catch (err) {
      setSaveTemplateError(err instanceof Error ? err.message : "Could not save template.");
    } finally {
      setSavingTemplate(false);
    }
  }

  function handleRenderAgain() {
    setJob(null);
    setJobId(null);
    setSubmitError(null);
  }

  async function handleCancelRender() {
    if (!job || cancelling) return;
    setCancelling(true);
    setCancelError(null);
    try {
      const updated = await cancelVideoComposeJob(job.id);
      setJob(updated);
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : "Could not cancel render.");
    } finally {
      setCancelling(false);
    }
  }

  async function handleRetryRender() {
    if (!job || retrying) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const newJob = await retryVideoComposeJob(job.id);
      setJob(newJob);
      setJobId(newJob.id);
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : "Could not retry render.");
    } finally {
      setRetrying(false);
    }
  }

  async function handleOpenOutputFolder() {
    if (!job) return;
    setOpenFolderError(null);
    try {
      await openVideoComposeJobFolder(job.id);
    } catch (err) {
      setOpenFolderError(err instanceof Error ? err.message : "Could not open folder.");
    }
  }

  const templateNameById: Record<string, string> = {};
  templates.forEach((t) => {
    templateNameById[t.id] = t.name;
  });

  const totalDuration = beats.reduce((sum, beat) => sum + beat.duration, 0);
  const readyBeatCount = beats.filter((beat) => beat.assetId != null).length;
  const hasNarration = beats.some((beat) => beat.narration.trim().length > 0);
  const audioSummary = [hasNarration ? "Narration" : null, musicPath.trim() ? "Music" : null]
    .filter(Boolean)
    .join(" + ") || "None";
  // Mirrors backend/app/api/v1/endpoints/composition_render.py's
  // _resolve_narration: ANY beat with a local narration asset switches the
  // whole render to narration_mode="local" (zero external calls); with
  // none, every beat falls back to edge_tts (1 external call, unknown
  // cost -- see docs/features/37-e2e-pipeline-hardening.md's accounting
  // rules). Purely a pre-render estimate; the real numbers come back on
  // the completed job's report (below).
  const usesLocalNarration = beats.some((beat) => beat.narrationAssetId != null);
  const estimatedExternalApiCalls = usesLocalNarration ? 0 : 1;
  // Deliberately not gated on readyBeatCount === beats.length: leaving the
  // button clickable when assets are missing lets handleSubmitRender's
  // validatePlan() surface the specific "Beat X: no asset assigned" errors
  // instead of a disabled button with no explanation.
  const canSubmit = beats.length > 0 && !submitting;
  const selectedBeat = beats.find((beat) => beat.id === selectedBeatId) ?? null;

  return (
    <div className="vf-page">
      <PageHeader
        title="Video Factory"
        subtitle={
          projectId != null
            ? `Editing batch project${projectName ? ` "${projectName}"` : ""} -- assign visuals, then render from the batch.`
            : "Turn a script into a captioned, narrated video from local images -- no cloud rendering."
        }
        actions={
          <div className="vf-header-actions">
            {beats.length > 0 && (
              <span className="vf-duration-badge">
                {Math.round(totalDuration)}s &bull; {ASPECT_RATIO_LABEL}
              </span>
            )}
            {batchIdParam && (
              <Link className="btn btn-secondary" to={`/batches/${batchIdParam}`}>
                <ArrowLeft size={14} />
                Back to Batch
              </Link>
            )}
            {projectId == null && (
              <button className="btn btn-secondary" onClick={handleOpenNewVideo}>
                <FilePlus2 size={14} />
                New Video
              </button>
            )}
            {beats.length > 0 && canSubmit && (
              <button className="btn btn-primary" onClick={handleQuickRender} disabled={submitting || qualityChecking}>
                {submitting || qualityChecking ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
                Quick Render
              </button>
            )}
          </div>
        }
      />

      <StepIndicator current={step} onSelect={goToStep} beatsReady={beats.length > 0} />

      {projectId != null && projectDataLoaded && (
        <ProductionProgress
          projectId={projectId}
          onRenderJobReady={(readyJobId) => {
            setJobId(readyJobId);
            setStep(5);
          }}
          onReviewBeat={(beatId) => {
            setSelectedBeatId(beatId);
            setStep(2);
          }}
        />
      )}

      {step === 1 && (
        <section className="vf-step-panel">
          <h2 className="vf-section-title">Script</h2>
          <label className="vf-field">
            <span>Project name</span>
            <input
              type="text"
              placeholder="My New Video"
              value={projectName}
              onChange={(e) => {
                setProjectName(e.target.value);
                setDirty(true);
              }}
            />
          </label>
          <textarea
            className="vf-textarea"
            rows={6}
            placeholder="Paste or type your narration script here. Tip: generate one on the AI Content page first, then paste it here."
            value={script}
            onChange={(e) => {
              setScript(e.target.value);
              setDirty(true);
            }}
          />
          {loadError && (
            <div className="vf-alert vf-alert-error">
              <AlertTriangle size={16} />
              Could not load your saved draft: {loadError}
            </div>
          )}
          <div className="vf-row">
            <button className="btn btn-primary" onClick={handleGenerateBeats} disabled={!script.trim() || generating}>
              {generating ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
              {generating ? "Generating beats..." : "Generate beats"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                addBeatManually();
                setStep(2);
              }}
              disabled={generating}
            >
              <Plus size={16} />
              Add beat manually
            </button>
          </div>
          {generateError && (
            <div className="vf-alert vf-alert-error">
              <AlertTriangle size={16} />
              {generateError}
            </div>
          )}
        </section>
      )}

      {(step === 2 || step === 3 || step === 4) && (
        <div className="vf-columns">
          <div className="vf-column-list">
            <div className="vf-column-header">
              <h2 className="vf-section-title">Beats</h2>
              <button className="btn btn-secondary vf-add-beat-btn" onClick={addBeatManually}>
                <Plus size={14} />
                Add beat
              </button>
            </div>

            <div className="vf-beat-plan-meta">
              <span className="vf-total-duration">Total duration: {totalDuration.toFixed(1)}s</span>
              <span className={`vf-dirty-indicator${dirty ? " dirty" : ""}`}>{dirty ? "Unsaved changes" : "Saved"}</span>
            </div>

            <button
              className="btn btn-primary vf-save-btn"
              onClick={handleSaveBeatPlan}
              disabled={beats.length === 0 || saving}
            >
              {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
              {saving ? "Saving..." : "Save"}
            </button>
            {saveError && (
              <div className="vf-alert vf-alert-error">
                <AlertTriangle size={14} />
                {saveError}
              </div>
            )}

            {beats.length === 0 ? (
              <EmptyState
                icon={Wand2}
                title="No beats yet"
                description="Generate beats from a script, or add one manually."
              />
            ) : (
              <ul className="vf-beat-list">
                {beats.map((beat, index) => (
                  <li key={beat.id}>
                    <button
                      className={`vf-beat-list-item${beat.id === selectedBeatId ? " active" : ""}`}
                      onClick={() => setSelectedBeatId(beat.id)}
                    >
                      <div className="vf-beat-list-item-top">
                        <span className="vf-beat-order">{String(index + 1).padStart(2, "0")}</span>
                        <span className="vf-beat-type-badge">{beat.type}</span>
                        <span className="vf-beat-duration">{beat.duration.toFixed(1)}s</span>
                      </div>
                      {beat.narration.trim() ? (
                        <p className="vf-beat-preview-text">{beat.narration}</p>
                      ) : (
                        <p className="vf-beat-warning">
                          <AlertTriangle size={11} /> No narration
                        </p>
                      )}
                      <div className="vf-beat-list-item-meta">
                        <span className={beat.assetStatus === "registered" ? "" : "vf-meta-missing"}>
                          <ImageIcon size={12} />
                          {beat.assetStatus === "registered" ? filenameFromPath(beat.assetPath) : "no asset"}
                        </span>
                        <span>
                          <Film size={12} />
                          {BEAT_MOTION_PRESET_LABELS[effectiveMotionPreset(beat.motionPreset, projectConfig)]}
                          {beat.motionPreset == null && <em className="vf-inherited-tag"> (default)</em>}
                        </span>
                        {!beat.visualHint && (
                          <span className="vf-meta-missing">
                            <AlertTriangle size={12} /> no visual hint
                          </span>
                        )}
                        {beat.narrationAssetStatus === "registered" && (
                          <span>
                            <Music size={12} />
                            {filenameFromPath(beat.narrationAssetPath)}
                          </span>
                        )}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="vf-column-detail">
            {!selectedBeat ? (
              <EmptyState
                icon={Clapperboard}
                title="No beat selected"
                description="Pick a beat from the list to edit it here."
              />
            ) : step === 2 ? (
              <BeatDetailsEditor
                beat={selectedBeat}
                index={beats.findIndex((b) => b.id === selectedBeat.id)}
                isFirst={beats[0]?.id === selectedBeat.id}
                isLast={beats[beats.length - 1]?.id === selectedBeat.id}
                onChange={(patch) => updateBeat(selectedBeat.id, patch)}
                onRemove={() => removeBeat(selectedBeat.id)}
                onMove={(direction) => moveBeat(selectedBeat.id, direction)}
              />
            ) : step === 3 ? (
              <VisualsEditor
                key={selectedBeat.id}
                beat={selectedBeat}
                job={job}
                projectConfig={projectConfig}
                onChange={(patch) => updateBeat(selectedBeat.id, patch)}
              />
            ) : (
              <NarrationEditor
                key={selectedBeat.id}
                beat={selectedBeat}
                onChange={(patch) => updateBeat(selectedBeat.id, patch)}
              />
            )}
          </div>
        </div>
      )}

      {step === 4 && (
        <section className="vf-step-panel">
          <div className="vf-project-defaults">
            <div className="vf-project-defaults-header">
              <span className="vf-field-label">
                Project defaults
                {projectConfig.template_id && (
                  <em className="vf-inherited-tag"> (from {templateNameById[projectConfig.template_id] ?? projectConfig.template_id})</em>
                )}
              </span>
              <button className="btn btn-secondary" onClick={() => setSaveTemplateOpen(true)}>
                <Save size={14} />
                Save as Template
              </button>
            </div>
            <label className="vf-field">
              <span>Default motion (used by any beat with no motion chosen)</span>
              <select
                value={projectConfig.motion.default_preset}
                onChange={(e) =>
                  setProjectConfig((prev) => ({
                    ...prev,
                    motion: { default_preset: e.target.value as BeatMotionPreset },
                  }))
                }
              >
                {BEAT_MOTION_PRESETS.map((preset) => (
                  <option key={preset} value={preset}>
                    {BEAT_MOTION_PRESET_LABELS[preset]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <h2 className="vf-section-title">Background music &amp; captions</h2>
          <p className="vf-field-label">
            Each beat's narration audio is chosen on the left. Beats with none set fall back to text-to-speech using
            the voice below.
          </p>
          <label className="vf-field">
            <span>Caption style</span>
            <select value={captionPreset} onChange={(e) => setCaptionPreset(e.target.value as CaptionPreset)}>
              {CAPTION_PRESETS.map((preset) => (
                <option key={preset} value={preset}>
                  {CAPTION_PRESET_LABELS[preset]}
                </option>
              ))}
            </select>
          </label>

          <div className="vf-grid">
            <label className="vf-field">
              <span>Narration voice (text-to-speech fallback)</span>
              <select value={voice} onChange={(e) => setVoice(e.target.value)}>
                {VOICE_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="vf-field">
              <span>Narration volume ({narrationVolume.toFixed(2)})</span>
              <input
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={narrationVolume}
                onChange={(e) => setNarrationVolume(Number(e.target.value))}
              />
            </label>
          </div>

          <h2 className="vf-section-title">Voice Factory (local narration)</h2>
          <p className="vf-field-label">
            One-Click Factory generates a real narration track from the script above using this voice, before Quality
            Check -- separate from the text-to-speech fallback above, which only applies at render time for beats with
            no narration audio assigned.
          </p>
          <div className="vf-grid">
            <label className="vf-field">
              <span>Provider</span>
              <select
                value={voiceProvider}
                onChange={(e) => {
                  const next = e.target.value as VoiceProjectConfig["provider"];
                  setVoiceProvider(next);
                  setVoiceId("default");
                }}
              >
                <option value="local">Local (offline, no network)</option>
                <option value="edge_tts">Edge TTS (free, requires network)</option>
              </select>
            </label>
            {voiceProvider === "local" ? (
              <label className="vf-field">
                <span>Voice</span>
                <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                  <option value="default">System Default</option>
                  {localVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
                {localVoicesError && (
                  <div className="vf-alert vf-alert-error">
                    <AlertTriangle size={14} />
                    {localVoicesError}
                  </div>
                )}
              </label>
            ) : (
              <label className="vf-field">
                <span>Voice</span>
                <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                  <option value="default">Default for language</option>
                  {VOICE_OPTIONS.map((v) => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="vf-field">
              <span>Speed ({voiceSpeed.toFixed(2)}x)</span>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={voiceSpeed}
                onChange={(e) => setVoiceSpeed(Number(e.target.value))}
              />
            </label>
          </div>

          <label className="vf-field">
            <span>Background music</span>
            <div className="vf-asset-row">
              <input
                type="text"
                placeholder="C:\Music\background.mp3"
                value={musicPath}
                onChange={(e) => {
                  setMusicPath(e.target.value);
                  setMusicAssetId(null);
                }}
              />
              <button className="btn btn-secondary" onClick={() => setMusicBrowserOpen(true)}>
                <Music size={14} />
                Choose Music
              </button>
              {musicPath.trim() && (
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setMusicPath("");
                    setMusicAssetId(null);
                  }}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
            {musicAssetId != null && <audio className="vf-audio-preview" src={assetFileUrl(musicAssetId)} controls preload="none" />}
          </label>

          <div className="vf-grid">
            <label className="vf-field">
              <span>Music volume ({musicVolume.toFixed(2)})</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={musicVolume}
                onChange={(e) => setMusicVolume(Number(e.target.value))}
                disabled={!musicPath.trim()}
              />
            </label>
            <label className="vf-field">
              <span>Music ducking under narration ({duckingRatio.toFixed(1)})</span>
              <input
                type="range"
                min={1}
                max={20}
                step={0.5}
                value={duckingRatio}
                onChange={(e) => setDuckingRatio(Number(e.target.value))}
                disabled={!musicPath.trim()}
              />
            </label>
            <label className="vf-field">
              <span>Fade in (sec)</span>
              <input
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={fadeIn}
                onChange={(e) => setFadeIn(Number(e.target.value))}
              />
            </label>
            <label className="vf-field">
              <span>Fade out (sec)</span>
              <input
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={fadeOut}
                onChange={(e) => setFadeOut(Number(e.target.value))}
              />
            </label>
          </div>

          {musicBrowserOpen && (
            <AssetBrowserModal
              assetType="audio"
              onSelect={(asset) => {
                setMusicPath(asset.path);
                setMusicAssetId(asset.id);
                setMusicBrowserOpen(false);
              }}
              onClose={() => setMusicBrowserOpen(false)}
            />
          )}
        </section>
      )}

      {step === 5 && (
        <section className="vf-step-panel">
          <h2 className="vf-section-title">Render summary</h2>

          <div className="vf-production-mode">
            <span className="vf-field-label">Production Mode</span>
            <div className="vf-production-mode-options">
              <span className="vf-production-mode-option active">
                <Check size={13} /> Local-first
              </span>
              <span className="vf-production-mode-option disabled" title="Not implemented -- local-first is the only production mode today">
                <Circle size={13} /> External AI (coming soon)
              </span>
            </div>
          </div>

          <div className="vf-render-summary">
            <div>
              <span>Beats</span>
              <strong>{beats.length}</strong>
            </div>
            <div>
              <span>Duration</span>
              <strong>{totalDuration.toFixed(1)}s</strong>
            </div>
            <div>
              <span>Resolution</span>
              <strong>
                {OUTPUT_FORMAT.width} &times; {OUTPUT_FORMAT.height}
              </strong>
            </div>
            <div>
              <span>Motion</span>
              <strong>Local</strong>
            </div>
            <div>
              <span>Audio</span>
              <strong>{audioSummary}</strong>
            </div>
            <div>
              <span>Assets assigned</span>
              <strong>
                {readyBeatCount} / {beats.length}
              </strong>
            </div>
            <div>
              <span>Captions</span>
              <strong>{usesLocalNarration ? "OFF (local narration)" : "ON"}</strong>
            </div>
            <div>
              <span>External API calls</span>
              <strong>{estimatedExternalApiCalls}</strong>
            </div>
            <div>
              <span>Estimated external cost</span>
              <strong>{estimatedExternalApiCalls === 0 ? "$0" : "Unknown"}</strong>
            </div>
          </div>

          <label className="vf-field">
            <span>Title</span>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="vf-field">
            <span>Output folder (optional -- defaults to the app's library folder)</span>
            <input
              type="text"
              placeholder="C:\Videos\Output"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
            />
          </label>

          {validationErrors.length > 0 && (
            <div className="vf-alert vf-alert-error">
              <AlertTriangle size={16} />
              <ul>
                {validationErrors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          {submitError && (
            <div className="vf-alert vf-alert-error">
              <AlertTriangle size={16} />
              {submitError}
            </div>
          )}

          {job && (
            <div className="vf-job-status-block">
              <div className="vf-job-status">
                {IN_PROGRESS_STATUSES.includes(job.status) && <Loader2 size={16} className="spin" />}
                {job.status === "completed" && <CheckCircle2 size={16} className="vf-status-ok" />}
                {job.status === "failed" && <XCircle size={16} className="vf-status-error" />}
                {job.status === "cancelled" && <Ban size={16} className="vf-status-error" />}
                <span>{STATUS_LABEL[job.status]}</span>
              </div>

              {IN_PROGRESS_STATUSES.includes(job.status) && (
                <>
                  <ul className="vf-phase-checklist">
                    {PHASE_ORDER.map(({ phase, label }) => {
                      const currentIndex = PHASE_ORDER.findIndex((p) => p.phase === job.phase);
                      const thisIndex = PHASE_ORDER.findIndex((p) => p.phase === phase);
                      const done = currentIndex >= 0 && thisIndex < currentIndex;
                      const active = phase === job.phase;
                      return (
                        <li key={phase} className={done ? "done" : active ? "active" : "pending"}>
                          {done ? <Check size={13} /> : active ? <Loader2 size={13} className="spin" /> : <Circle size={13} />}
                          <span>
                            {active && phase === "RENDER_BEATS" && job.progress_current != null && job.progress_total != null
                              ? `Rendering Beat ${job.progress_current} / ${job.progress_total}`
                              : label}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                  <button className="btn btn-secondary" onClick={handleCancelRender} disabled={cancelling}>
                    {cancelling ? <Loader2 size={14} className="spin" /> : <Ban size={14} />}
                    Cancel
                  </button>
                  {cancelError && (
                    <div className="vf-alert vf-alert-error">
                      <AlertTriangle size={14} />
                      {cancelError}
                    </div>
                  )}
                </>
              )}

              {job.status === "failed" && job.error_message && (
                <div className="vf-alert vf-alert-error">
                  <AlertTriangle size={16} />
                  <span>
                    {job.failed_phase && <strong>[{job.failed_phase}] </strong>}
                    {job.error_message}
                  </span>
                </div>
              )}

              {job.status === "cancelled" && <p className="vf-field-label">This render was cancelled.</p>}

              {job.status === "completed" && job.output_media_url && (
                <>
                  <video className="vf-job-preview" src={mediaUrl(job.output_media_url)} controls preload="metadata" />
                  <span className="vf-job-preview-meta">
                    {(job.render_duration_sec ?? totalDuration).toFixed(1)}s &bull; {job.render_width ?? OUTPUT_FORMAT.width}
                    &times;{job.render_height ?? OUTPUT_FORMAT.height}
                    {job.output_size_mb != null && <> &bull; {job.output_size_mb.toFixed(1)} MB</>}
                  </span>
                  <span className="vf-job-preview-meta">
                    External API calls: {job.external_api_calls ?? estimatedExternalApiCalls} &bull; External cost:{" "}
                    {(job.external_api_calls ?? estimatedExternalApiCalls) === 0
                      ? "$0"
                      : job.external_api_cost_estimate != null
                        ? `$${job.external_api_cost_estimate}`
                        : "Unknown"}
                  </span>
                  <div className="vf-row">
                    <button className="btn btn-secondary" onClick={handleOpenOutputFolder}>
                      <FolderOpen size={14} />
                      Open Folder
                    </button>
                    <button className="btn btn-secondary" onClick={handleRenderAgain}>
                      <RotateCcw size={14} />
                      Render Again
                    </button>
                  </div>
                  {openFolderError && (
                    <div className="vf-alert vf-alert-error">
                      <AlertTriangle size={14} />
                      {openFolderError}
                    </div>
                  )}
                </>
              )}
              {(job.status === "failed" || job.status === "cancelled") && (
                <div className="vf-row">
                  <button className="btn btn-secondary" onClick={handleRenderAgain}>
                    <RotateCcw size={14} />
                    Fix (edit &amp; resubmit)
                  </button>
                  <button className="btn btn-secondary" onClick={handleRetryRender} disabled={retrying}>
                    {retrying ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />}
                    Retry
                  </button>
                </div>
              )}
              {retryError && (
                <div className="vf-alert vf-alert-error">
                  <AlertTriangle size={14} />
                  {retryError}
                </div>
              )}
            </div>
          )}

          {recentJobs.length > 0 && (
            <div className="vf-recent-renders">
              <h3 className="vf-section-title">Recent renders</h3>
              <ul className="vf-recent-renders-list">
                {recentJobs.map((recentJob) => (
                  <li key={recentJob.id}>
                    <span className="vf-recent-render-title">
                      #{recentJob.id.toString().padStart(3, "0")} {recentJob.title}
                    </span>
                    <span className={`vf-recent-render-status vf-recent-render-status-${recentJob.job_status.toLowerCase()}`}>
                      {recentJob.job_status === "RUNNING" && recentJob.phase ? recentJob.phase.replace(/_/g, " ") : recentJob.job_status}
                    </span>
                    {(recentJob.job_status === "QUEUED" || recentJob.job_status === "RUNNING") && (
                      <button
                        className="btn btn-secondary vf-recent-render-cancel"
                        onClick={async () => {
                          await cancelVideoComposeJob(recentJob.id).catch(() => undefined);
                          refreshRecentJobs();
                          if (recentJob.id === job?.id) getVideoComposeJob(recentJob.id).then(setJob).catch(() => undefined);
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <div className="vf-bottom-bar">
        <button className="btn btn-secondary" onClick={() => goToStep((Math.max(1, step - 1) as Step))} disabled={step === 1}>
          Back
        </button>
        {step < 5 ? (
          <button className="btn btn-primary" onClick={() => goToStep((Math.min(5, step + 1) as Step))}>
            Next
          </button>
        ) : (
          <button
            className="btn btn-primary vf-render-btn"
            onClick={() => handleSubmitRender()}
            disabled={!canSubmit || qualityChecking}
          >
            {submitting || qualityChecking ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
            {qualityChecking ? "Checking..." : "Render Video"}
          </button>
        )}
      </div>

      {qualityCheckError && <div className="vf-alert vf-alert-error">{qualityCheckError}</div>}

      {qualityCheckOpen && qualityReport && (
        <ProductionCheckModal
          report={qualityReport}
          submitting={submitting}
          onSelectBeat={(beatId) => {
            const beat = beats.find((b) => b.id === beatId);
            if (beat) setSelectedBeatId(beat.id);
            setStep(2);
            setQualityCheckOpen(false);
          }}
          onRenderAnyway={() => {
            setQualityCheckOpen(false);
            handleSubmitRender(true);
          }}
          onClose={() => setQualityCheckOpen(false)}
        />
      )}

      {templatePickerOpen && (
        <TemplatePickerModal
          templates={templates}
          error={templatesError}
          onRetry={refreshTemplates}
          onSelect={handleUseTemplate}
          onClose={() => setTemplatePickerOpen(false)}
        />
      )}

      {saveTemplateOpen && (
        <div className="vf-modal-backdrop" onClick={() => setSaveTemplateOpen(false)}>
          <div className="vf-modal vf-save-template-modal" onClick={(e) => e.stopPropagation()}>
            <div className="vf-modal-header">
              <h3>Save as Template</h3>
              <button className="btn btn-icon" onClick={() => setSaveTemplateOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <p className="vf-field-label">
              Saves the current motion/caption/audio settings only -- not your script, beats, assets, or this
              project's name.
            </p>
            <label className="vf-field">
              <span>Name</span>
              <input
                type="text"
                placeholder="Colombia Emotional V2"
                value={saveTemplateName}
                onChange={(e) => setSaveTemplateName(e.target.value)}
                autoFocus
              />
            </label>
            {saveTemplateError && (
              <div className="vf-alert vf-alert-error">
                <AlertTriangle size={14} />
                {saveTemplateError}
              </div>
            )}
            <div className="vf-row">
              <button
                className="btn btn-primary"
                onClick={handleSaveAsTemplate}
                disabled={!saveTemplateName.trim() || savingTemplate}
              >
                {savingTemplate ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
                Save Template
              </button>
              <button className="btn btn-secondary" onClick={() => setSaveTemplateOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -- Task 16: Production Check (see docs/features/42-content-quality-gate.md) --

interface ProductionCheckModalProps {
  report: QualityReport;
  submitting: boolean;
  onSelectBeat: (beatId: string) => void;
  onRenderAnyway: () => void;
  onClose: () => void;
}

const DIMENSION_KEYS: (keyof QualityReport["dimensions"])[] = [
  "narrative", "pacing", "visual", "motion", "audio", "captions",
];

function ProductionCheckModal({ report, submitting, onSelectBeat, onRenderAnyway, onClose }: ProductionCheckModalProps) {
  const blocked = report.status === "BLOCKED";
  return (
    <div className="vf-modal-backdrop" onClick={onClose}>
      <div className="vf-modal vf-quality-modal" onClick={(e) => e.stopPropagation()}>
        <div className="vf-modal-header">
          <h3>{blocked ? "Production Blocked" : "Production Check"}</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {!blocked && (
          <div className="vf-quality-score">
            <span className="vf-quality-score-value">{report.score}</span>
            <span className="vf-quality-score-max">/ 100</span>
            <span className="vf-quality-score-label">Readiness Score</span>
          </div>
        )}

        {!blocked && (
          <div className="vf-quality-dimensions">
            {DIMENSION_KEYS.map((key) => {
              const value = report.dimensions[key];
              const ok = value >= 90;
              return (
                <div key={key} className={`vf-quality-dimension${ok ? " ok" : " warn"}`}>
                  {ok ? <Check size={13} /> : <AlertTriangle size={13} />}
                  <span>{DIMENSION_LABELS[key]}</span>
                  <span className="vf-quality-dimension-value">{value}</span>
                </div>
              );
            })}
          </div>
        )}

        {report.issues.length > 0 && (
          <div className="vf-quality-issue-group">
            <h4>{report.issues.length} Critical</h4>
            {report.issues.map((issue, i) => (
              <button
                key={i}
                className="vf-quality-issue vf-quality-issue-error"
                onClick={() => issue.beat_id && onSelectBeat(issue.beat_id)}
                disabled={!issue.beat_id}
              >
                <XCircle size={13} />
                {issue.message}
              </button>
            ))}
          </div>
        )}

        {report.warnings.length > 0 && (
          <div className="vf-quality-issue-group">
            <h4>{report.warnings.length} Warning{report.warnings.length === 1 ? "" : "s"}</h4>
            {report.warnings.map((warning, i) => (
              <button
                key={i}
                className="vf-quality-issue vf-quality-issue-warning"
                onClick={() => warning.beat_id && onSelectBeat(warning.beat_id)}
                disabled={!warning.beat_id}
              >
                <AlertTriangle size={13} />
                {warning.message}
              </button>
            ))}
          </div>
        )}

        <div className="vf-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            {blocked ? "Fix Issues" : "Review"}
          </button>
          {!blocked && (
            <button className="btn btn-primary" onClick={onRenderAnyway} disabled={submitting}>
              {submitting ? <Loader2 size={14} className="spin" /> : null}
              Render Anyway
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface TemplatePickerModalProps {
  templates: Template[];
  error: string | null;
  onRetry: () => void;
  onSelect: (template: Template) => void;
  onClose: () => void;
}

// Task 12 section 16 -- a lightweight template selector, not a full
// marketplace: name/description/render profile/caption style/motion
// style per card, built-ins visually distinguished from custom ones (see
// section 17). No generated thumbnails, no AI image call.
function TemplatePickerModal({ templates, error, onRetry, onSelect, onClose }: TemplatePickerModalProps) {
  return (
    <div className="vf-modal-backdrop" onClick={onClose}>
      <div className="vf-modal vf-template-picker-modal" onClick={(e) => e.stopPropagation()}>
        <div className="vf-modal-header">
          <h3>Choose Template</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="vf-alert vf-alert-error">
            <AlertTriangle size={16} />
            <span>
              {error}
              <button className="btn btn-secondary" onClick={onRetry}>
                Retry
              </button>
            </span>
          </div>
        )}

        {templates.length === 0 && !error ? (
          <p className="vf-field-label">Loading templates...</p>
        ) : (
          <div className="vf-template-grid">
            {templates.map((template) => (
              <div key={template.id} className="vf-template-card">
                <div className="vf-template-card-header">
                  <strong>{template.name}</strong>
                  <span className={`vf-template-badge ${template.builtin ? "builtin" : "custom"}`}>
                    {template.builtin ? "Built-in" : "Custom"}
                  </span>
                </div>
                <p className="vf-template-description">{template.description || "No description."}</p>
                <ul className="vf-template-facts">
                  <li>
                    <Film size={12} /> {template.config.render.profile === "SOCIAL_VERTICAL" ? "9:16" : template.config.render.profile}
                  </li>
                  <li>
                    <Sparkles size={12} /> {CAPTION_PRESET_LABELS[template.config.captions.preset]} captions
                  </li>
                  <li>
                    <Clapperboard size={12} /> {BEAT_MOTION_PRESET_LABELS[template.config.motion.default_preset]} motion
                  </li>
                  <li>
                    <Music size={12} /> {template.config.audio.music_enabled ? "Local music" : "No music"} &bull;{" "}
                    {template.config.audio.narration_enabled ? "Local narration" : "No narration"}
                  </li>
                </ul>
                <button className="btn btn-primary vf-template-use-btn" onClick={() => onSelect(template)}>
                  Use Template
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface StepIndicatorProps {
  current: Step;
  onSelect: (step: Step) => void;
  beatsReady: boolean;
}

function StepIndicator({ current, onSelect, beatsReady }: StepIndicatorProps) {
  return (
    <div className="vf-stepper">
      {STEPS.map((s, index) => {
        const isDone = s.id < current || (s.id === 1 && beatsReady && current > 1);
        const isCurrent = s.id === current;
        return (
          <div className="vf-stepper-item" key={s.id}>
            <button
              className={`vf-stepper-dot${isCurrent ? " current" : ""}${isDone ? " done" : ""}`}
              onClick={() => onSelect(s.id)}
              title={s.label}
            >
              {isDone ? <Check size={13} /> : s.id}
            </button>
            <span className={`vf-stepper-label${isCurrent ? " current" : ""}`}>{s.label}</span>
            {index < STEPS.length - 1 && <span className={`vf-stepper-line${isDone ? " done" : ""}`} />}
          </div>
        );
      })}
    </div>
  );
}

interface BeatDetailsEditorProps {
  beat: WorkingBeat;
  index: number;
  isFirst: boolean;
  isLast: boolean;
  onChange: (patch: Partial<WorkingBeat>) => void;
  onRemove: () => void;
  onMove: (direction: -1 | 1) => void;
}

function BeatDetailsEditor({ beat, index, isFirst, isLast, onChange, onRemove, onMove }: BeatDetailsEditorProps) {
  return (
    <div className="vf-detail-card">
      <div className="vf-beat-header">
        <span className="vf-beat-index">#{index + 1}</span>
        <select value={beat.type} onChange={(e) => onChange({ type: e.target.value as BeatType })}>
          {BEAT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <div className="vf-beat-header-actions">
          <button className="btn btn-secondary" onClick={() => onMove(-1)} disabled={isFirst} title="Move up">
            <ArrowUp size={14} />
          </button>
          <button className="btn btn-secondary" onClick={() => onMove(1)} disabled={isLast} title="Move down">
            <ArrowDown size={14} />
          </button>
          <button className="btn btn-secondary" onClick={onRemove} title="Remove beat">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <label className="vf-field">
        <span>Narration</span>
        <textarea rows={4} value={beat.narration} onChange={(e) => onChange({ narration: e.target.value })} />
        {!beat.narration.trim() && (
          <span className="vf-field-warning">
            <AlertTriangle size={12} /> No narration
          </span>
        )}
      </label>

      <label className="vf-field">
        <span>Visual hint</span>
        <input
          type="text"
          placeholder="e.g. woman waiting alone at home"
          value={beat.visualHint ?? ""}
          onChange={(e) => onChange({ visualHint: e.target.value || null })}
        />
        {!beat.visualHint?.trim() && (
          <span className="vf-field-warning">
            <AlertTriangle size={12} /> No visual hint
          </span>
        )}
      </label>

      <label className="vf-field">
        <span>Duration (sec)</span>
        <input
          type="number"
          min={0.1}
          max={120}
          step={0.1}
          value={beat.duration}
          onChange={(e) => onChange({ duration: Number(e.target.value) })}
        />
      </label>
    </div>
  );
}

interface VisualsEditorProps {
  beat: WorkingBeat;
  job: VideoComposeJob | null;
  projectConfig: ProjectConfig;
  onChange: (patch: Partial<WorkingBeat>) => void;
}

function VisualsEditor({ beat, job, projectConfig, onChange }: VisualsEditorProps) {
  const [browserOpen, setBrowserOpen] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<BeatPreviewResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const finishedPreviewUrl = job?.status === "completed" && job.output_media_url ? mediaUrl(job.output_media_url) : null;
  const resolvedMotionPreset = effectiveMotionPreset(beat.motionPreset, projectConfig);

  function handleAssetSelected(asset: Asset) {
    onChange({ assetId: asset.id, assetPath: asset.path, assetStatus: "registered", assetError: null });
    setBrowserOpen(false);
  }

  function handleRemoveAsset() {
    onChange({ assetId: null, assetPath: "", assetStatus: "unregistered", assetError: null });
  }

  async function handlePreviewMotion() {
    if (beat.assetId == null || previewing) return;
    setPreviewing(true);
    setPreviewError(null);
    try {
      const result = await renderBeatPreview({
        asset_id: beat.assetId,
        motion_preset: resolvedMotionPreset,
        duration: beat.duration,
      });
      setPreviewResult(result);
    } catch (err) {
      // The backend's own error can include raw ffmpeg stderr (logged
      // server-side already) -- never show that verbatim to the user.
      console.error("Beat motion preview failed:", err);
      setPreviewError("Unable to render preview.");
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <div className="vf-detail-card">
      <span className="vf-field-label">Selected asset</span>
      <div className="vf-asset-preview-box">
        {beat.assetStatus === "registered" && beat.assetId != null ? (
          <img src={assetFileUrl(beat.assetId)} alt="" />
        ) : beat.assetStatus === "error" ? (
          <div className="vf-preview-placeholder vf-preview-error">
            <AlertTriangle size={24} />
            <strong>Asset unavailable</strong>
            <span>{beat.assetError ?? "The selected image is no longer available in the Library."}</span>
          </div>
        ) : (
          <div className="vf-preview-placeholder">
            <ImageIcon size={24} />
            <span>No asset selected</span>
          </div>
        )}
      </div>

      <div className="vf-row">
        <button className="btn btn-primary" onClick={() => setBrowserOpen(true)}>
          <ImageIcon size={14} />
          {beat.assetStatus === "registered" ? "Change asset" : "Choose asset"}
        </button>
        {beat.assetId != null && (
          <button className="btn btn-secondary" onClick={handleRemoveAsset}>
            <Trash2 size={14} />
            Remove asset
          </button>
        )}
      </div>

      <label className="vf-field">
        <span>Visual hint</span>
        <p className="vf-visual-hint-readout">{beat.visualHint ? `"${beat.visualHint}"` : "No visual hint set for this beat."}</p>
      </label>

      <label className="vf-field">
        <span>Motion{beat.motionPreset == null && <em className="vf-inherited-tag"> (using project default)</em>}</span>
        <select value={resolvedMotionPreset} onChange={(e) => onChange({ motionPreset: e.target.value as BeatMotionPreset })}>
          {BEAT_MOTION_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {BEAT_MOTION_PRESET_LABELS[preset]}
            </option>
          ))}
        </select>
        <p className="vf-motion-description">{BEAT_MOTION_PRESET_DESCRIPTIONS[resolvedMotionPreset]}</p>
      </label>

      <button
        className="btn btn-secondary vf-preview-btn"
        onClick={handlePreviewMotion}
        disabled={beat.assetId == null || previewing}
        title={beat.assetId == null ? "Choose an asset first" : undefined}
      >
        {previewing ? <Loader2 size={14} className="spin" /> : <Clapperboard size={14} />}
        {previewing ? "Rendering preview..." : "Preview motion"}
      </button>

      {previewResult && (
        <div className="vf-motion-preview">
          <video src={mediaUrl(previewResult.preview_media_url)} controls autoPlay loop />
          <span className="vf-motion-preview-meta">
            {previewResult.duration.toFixed(1)}s &bull; {previewResult.width}&times;{previewResult.height}
          </span>
        </div>
      )}
      {previewError && (
        <div className="vf-preview-placeholder vf-preview-error">
          <AlertTriangle size={18} />
          <span>{previewError}</span>
          <button className="btn btn-secondary" onClick={handlePreviewMotion}>
            Retry
          </button>
        </div>
      )}

      {finishedPreviewUrl && (
        <div className="vf-preview-box">
          <video src={finishedPreviewUrl} controls preload="metadata" />
        </div>
      )}

      {browserOpen && (
        <AssetBrowserModal
          initialQuery={beat.visualHint ?? ""}
          onSelect={handleAssetSelected}
          onClose={() => setBrowserOpen(false)}
        />
      )}
    </div>
  );
}

interface NarrationEditorProps {
  beat: WorkingBeat;
  onChange: (patch: Partial<WorkingBeat>) => void;
}

function NarrationEditor({ beat, onChange }: NarrationEditorProps) {
  const [browserOpen, setBrowserOpen] = useState(false);

  function handleNarrationSelected(asset: Asset) {
    onChange({
      narrationAssetId: asset.id,
      narrationAssetPath: asset.path,
      narrationAssetStatus: "registered",
      narrationAssetError: null,
    });
    setBrowserOpen(false);
  }

  function handleRemoveNarration() {
    onChange({
      narrationAssetId: null,
      narrationAssetPath: "",
      narrationAssetStatus: "unregistered",
      narrationAssetError: null,
    });
  }

  return (
    <div className="vf-detail-card">
      <span className="vf-field-label">Narration</span>

      {beat.narrationAssetStatus === "registered" && beat.narrationAssetId != null ? (
        <audio className="vf-audio-preview" src={assetFileUrl(beat.narrationAssetId)} controls preload="metadata" />
      ) : beat.narrationAssetStatus === "error" ? (
        <div className="vf-preview-placeholder vf-preview-error">
          <AlertTriangle size={20} />
          <span>{beat.narrationAssetError ?? "The selected audio is no longer available in the Library."}</span>
        </div>
      ) : (
        <p className="vf-visual-hint-readout">
          No local narration audio set -- this beat's text will be read aloud via text-to-speech instead.
        </p>
      )}

      <div className="vf-row">
        <button className="btn btn-primary" onClick={() => setBrowserOpen(true)}>
          <Music size={14} />
          {beat.narrationAssetStatus === "registered" ? "Change audio" : "Choose Audio"}
        </button>
        {beat.narrationAssetId != null && (
          <button className="btn btn-secondary" onClick={handleRemoveNarration}>
            <Trash2 size={14} />
            Remove audio
          </button>
        )}
      </div>

      <label className="vf-field">
        <span>Beat narration text</span>
        <p className="vf-visual-hint-readout">{beat.narration.trim() ? `"${beat.narration}"` : "No narration text for this beat."}</p>
      </label>

      {browserOpen && (
        <AssetBrowserModal assetType="audio" onSelect={handleNarrationSelected} onClose={() => setBrowserOpen(false)} />
      )}
    </div>
  );
}
