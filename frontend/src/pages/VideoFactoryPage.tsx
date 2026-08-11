import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Loader2,
  Plus,
  Trash2,
  Wand2,
  XCircle,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { registerAsset, searchAssets } from "../api/asset";
import { getVideoComposeJob } from "../api/videoComposer";
import { renderComposition } from "../api/videoFactory";
import { mediaUrl } from "../api/client";
import type { AssetType } from "../types/asset";
import type { VideoComposeJob } from "../types/videoComposer";
import {
  BEAT_TYPES,
  CAPTION_PRESETS,
  CAPTION_PRESET_LABELS,
  MOTION_PRESETS,
  MOTION_PRESET_DEFAULTS,
  MOTION_PRESET_LABELS,
} from "../types/videoFactory";
import type { BeatType, CaptionPreset, MotionPresetName, OutputFormat, Scene, WorkingBeat } from "../types/videoFactory";
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
const WORDS_PER_MINUTE = 150;
const MIN_BEAT_DURATION = 1.5;
const MAX_BEAT_DURATION = 12;
const POLL_INTERVAL_MS = 2000;

const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff", "tif"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "mov", "mkv", "webm", "avi"]);

const STATUS_LABEL: Record<VideoComposeJob["status"], string> = {
  queued: "Queued",
  merging: "Merging clips",
  narrating: "Generating narration",
  subtitling: "Generating captions",
  mixing_audio: "Mixing audio",
  finalizing: "Finalizing",
  completed: "Completed",
  failed: "Failed",
};
const IN_PROGRESS_STATUSES: VideoComposeJob["status"][] = [
  "queued",
  "merging",
  "narrating",
  "subtitling",
  "mixing_audio",
  "finalizing",
];

let beatIdCounter = 0;
function nextBeatId(): string {
  beatIdCounter += 1;
  return `beat_${beatIdCounter}_${Date.now()}`;
}

function splitIntoSentences(script: string): string[] {
  return script
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 0);
}

function estimateDuration(text: string): number {
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const seconds = (wordCount / WORDS_PER_MINUTE) * 60;
  return Math.min(MAX_BEAT_DURATION, Math.max(MIN_BEAT_DURATION, Math.round(seconds * 10) / 10));
}

function beatTypeForIndex(index: number, total: number): BeatType {
  if (index === 0) return "hook";
  if (total > 1 && index === total - 1) return "cta";
  return "body";
}

function makeBeat(overrides: Partial<WorkingBeat> = {}): WorkingBeat {
  return {
    id: nextBeatId(),
    order: 1,
    type: "body",
    narration: "",
    duration: 3,
    motionPreset: "zoom_and_pan",
    assetPath: "",
    assetId: null,
    assetStatus: "unregistered",
    assetError: null,
    ...overrides,
  };
}

function generateBeatsFromScript(script: string): WorkingBeat[] {
  const sentences = splitIntoSentences(script);
  return sentences.map((sentence, index) =>
    makeBeat({
      order: index + 1,
      type: beatTypeForIndex(index, sentences.length),
      narration: sentence,
      duration: estimateDuration(sentence),
      motionPreset: MOTION_PRESETS[index % MOTION_PRESETS.length],
    })
  );
}

function inferAssetType(path: string): AssetType {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  if (VIDEO_EXTENSIONS.has(ext)) return "video";
  if (IMAGE_EXTENSIONS.has(ext)) return "image";
  return "image";
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

function buildScene(beat: WorkingBeat, order: number, captionPreset: CaptionPreset): Scene {
  const motionDefaults = MOTION_PRESET_DEFAULTS[beat.motionPreset];
  return {
    id: beat.id,
    order,
    beat_id: beat.id,
    duration: beat.duration,
    source_asset_id: beat.assetId as number,
    motion: {
      preset_name: beat.motionPreset,
      scale: motionDefaults.scale,
      position: motionDefaults.position,
      rotation: motionDefaults.rotation,
      easing: "ease_in_out",
    },
    caption: { text: beat.narration, preset: captionPreset },
    audio: { sfx: null, sfx_volume: 1.0 },
    transition: { type: "crossfade", duration: 0.4 },
    output_format: OUTPUT_FORMAT,
  };
}

function buildCompositionPlan(
  beats: WorkingBeat[],
  settings: AudioCaptionSettings
): { plan: CompositionPlan; assetPaths: Record<number, string> } {
  const scenes = beats.map((beat, index) => buildScene(beat, index + 1, settings.captionPreset));
  const assetPaths: Record<number, string> = {};
  beats.forEach((beat) => {
    if (beat.assetId != null) assetPaths[beat.assetId] = beat.assetPath.trim();
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
  return { plan, assetPaths };
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
    if (beat.assetId == null) errors.push(`${label}: no asset assigned -- enter a file path and click "Register".`);
  });
  return errors;
}

export function VideoFactoryPage() {
  const [script, setScript] = useState("");
  const [beats, setBeats] = useState<WorkingBeat[]>([]);

  const [title, setTitle] = useState("Video Factory Composition");
  const [voice, setVoice] = useState(VOICE_OPTIONS[0].value);
  const [narrationVolume, setNarrationVolume] = useState(1.0);
  const [musicPath, setMusicPath] = useState("");
  const [musicVolume, setMusicVolume] = useState(0.15);
  const [duckingRatio, setDuckingRatio] = useState(8.0);
  const [fadeIn, setFadeIn] = useState(0.0);
  const [fadeOut, setFadeOut] = useState(0.0);
  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>("emotional");
  const [outputDir, setOutputDir] = useState("");

  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<VideoComposeJob | null>(null);

  useEffect(() => {
    if (jobId == null) return;
    let cancelled = false;

    async function poll() {
      try {
        const data = await getVideoComposeJob(jobId as number);
        if (!cancelled) setJob(data);
      } catch {
        // Ignore a transient polling error; try again on the next tick.
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId]);

  function handleGenerateBeats() {
    setBeats(generateBeatsFromScript(script));
    setValidationErrors([]);
  }

  function updateBeat(id: string, patch: Partial<WorkingBeat>) {
    setBeats((prev) => prev.map((beat) => (beat.id === id ? { ...beat, ...patch } : beat)));
  }

  function removeBeat(id: string) {
    setBeats((prev) => prev.filter((beat) => beat.id !== id));
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
  }

  function addBeatManually() {
    setBeats((prev) => [...prev, makeBeat({ order: prev.length + 1 })]);
  }

  async function handleRegisterAsset(beatId: string) {
    const beat = beats.find((b) => b.id === beatId);
    if (!beat) return;
    const path = beat.assetPath.trim();
    if (!path) {
      updateBeat(beatId, { assetStatus: "error", assetError: "Enter a file path first." });
      return;
    }
    updateBeat(beatId, { assetStatus: "registering", assetError: null });
    try {
      const asset = await registerAsset({
        filename: filenameFromPath(path),
        path,
        type: inferAssetType(path),
      });
      updateBeat(beatId, { assetId: asset.id, assetStatus: "registered", assetError: null });
    } catch (err) {
      // Asset paths are unique (see backend/app/modules/asset -- a file can
      // only be registered once); the same image being reused across beats,
      // or the user retrying registration, is a normal flow, not a real
      // error. Look the existing asset up by path instead of failing hard.
      try {
        const matches = await searchAssets(filenameFromPath(path));
        const existing = matches.find((a) => a.path.toLowerCase() === path.toLowerCase());
        if (existing) {
          updateBeat(beatId, { assetId: existing.id, assetStatus: "registered", assetError: null });
          return;
        }
      } catch {
        // Fall through to reporting the original registration error below.
      }
      updateBeat(beatId, {
        assetStatus: "error",
        assetError: err instanceof Error ? err.message : "Could not register asset.",
      });
    }
  }

  async function handleSubmitRender() {
    const errors = validatePlan(beats, script);
    setValidationErrors(errors);
    if (errors.length > 0) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const { plan, assetPaths } = buildCompositionPlan(beats, {
        voice,
        narrationVolume,
        musicPath,
        musicVolume,
        duckingRatio,
        fadeIn,
        fadeOut,
        captionPreset,
      });
      const result = await renderComposition({
        plan,
        asset_paths: assetPaths,
        title: title.trim() || "Video Factory Composition",
        output_dir: outputDir.trim() || undefined,
      });
      setJob(result);
      setJobId(result.id);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not start render.");
    } finally {
      setSubmitting(false);
    }
  }

  const totalDuration = beats.reduce((sum, beat) => sum + beat.duration, 0);
  const readyBeatCount = beats.filter((beat) => beat.assetId != null).length;
  const canSubmit = beats.length > 0 && readyBeatCount === beats.length && !submitting;

  return (
    <div className="vf-page">
      <PageHeader
        title="Video Factory"
        subtitle="Turn a script into a captioned, narrated video from local images -- no cloud rendering."
      />

      <section className="vf-section">
        <h2 className="vf-section-title">1. Script</h2>
        <textarea
          className="vf-textarea"
          rows={4}
          placeholder="Paste or type your narration script here. Tip: generate one on the AI Content page first, then paste it here."
          value={script}
          onChange={(e) => setScript(e.target.value)}
        />
        <div className="vf-row">
          <button className="btn btn-primary" onClick={handleGenerateBeats} disabled={!script.trim()}>
            <Wand2 size={16} />
            Generate beats
          </button>
          <button className="btn btn-secondary" onClick={addBeatManually}>
            <Plus size={16} />
            Add beat manually
          </button>
        </div>
      </section>

      <section className="vf-section">
        <h2 className="vf-section-title">2. Beats</h2>
        {beats.length === 0 ? (
          <EmptyState
            icon={Wand2}
            title="No beats yet"
            description="Generate beats from a script above, or add one manually."
          />
        ) : (
          <div className="vf-beats">
            {beats.map((beat, index) => (
              <BeatCard
                key={beat.id}
                beat={beat}
                index={index}
                isFirst={index === 0}
                isLast={index === beats.length - 1}
                onChange={(patch) => updateBeat(beat.id, patch)}
                onRemove={() => removeBeat(beat.id)}
                onMove={(direction) => moveBeat(beat.id, direction)}
                onRegisterAsset={() => handleRegisterAsset(beat.id)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="vf-section">
        <h2 className="vf-section-title">3. Captions</h2>
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
      </section>

      <section className="vf-section">
        <h2 className="vf-section-title">4. Audio</h2>
        <div className="vf-grid">
          <label className="vf-field">
            <span>Narration voice</span>
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
          <label className="vf-field">
            <span>Background music file path (optional)</span>
            <input
              type="text"
              placeholder="C:\Music\background.mp3"
              value={musicPath}
              onChange={(e) => setMusicPath(e.target.value)}
            />
          </label>
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
      </section>

      <section className="vf-section">
        <h2 className="vf-section-title">5. Review &amp; render</h2>
        <div className="vf-summary">
          <div>
            <strong>{beats.length}</strong> beat{beats.length === 1 ? "" : "s"}
          </div>
          <div>
            <strong>{totalDuration.toFixed(1)}s</strong> estimated total duration
          </div>
          <div>
            <strong>{readyBeatCount}</strong> / {beats.length} assets assigned
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

        <button className="btn btn-primary" onClick={handleSubmitRender} disabled={!canSubmit}>
          {submitting ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
          Render video
        </button>
      </section>

      {job && (
        <section className="vf-section">
          <h2 className="vf-section-title">6. Output</h2>
          <div className="vf-job-status">
            {IN_PROGRESS_STATUSES.includes(job.status) && <Loader2 size={16} className="spin" />}
            {job.status === "completed" && <CheckCircle2 size={16} className="vf-status-ok" />}
            {job.status === "failed" && <XCircle size={16} className="vf-status-error" />}
            <span>{STATUS_LABEL[job.status]}</span>
          </div>

          {job.status === "failed" && job.error_message && (
            <div className="vf-alert vf-alert-error">
              <AlertTriangle size={16} />
              {job.error_message}
            </div>
          )}

          {job.status === "completed" && job.output_media_url && (
            <video className="vf-job-preview" src={mediaUrl(job.output_media_url)} controls preload="metadata" />
          )}
        </section>
      )}
    </div>
  );
}

interface BeatCardProps {
  beat: WorkingBeat;
  index: number;
  isFirst: boolean;
  isLast: boolean;
  onChange: (patch: Partial<WorkingBeat>) => void;
  onRemove: () => void;
  onMove: (direction: -1 | 1) => void;
  onRegisterAsset: () => void;
}

function BeatCard({ beat, index, isFirst, isLast, onChange, onRemove, onMove, onRegisterAsset }: BeatCardProps) {
  return (
    <div className="vf-beat-card">
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
        <textarea rows={2} value={beat.narration} onChange={(e) => onChange({ narration: e.target.value })} />
      </label>

      <div className="vf-grid">
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
        <label className="vf-field">
          <span>Motion preset</span>
          <select
            value={beat.motionPreset}
            onChange={(e) => onChange({ motionPreset: e.target.value as MotionPresetName })}
          >
            {MOTION_PRESETS.map((preset) => (
              <option key={preset} value={preset}>
                {MOTION_PRESET_LABELS[preset]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="vf-field">
        <span>Image file path</span>
        <div className="vf-asset-row">
          <input
            type="text"
            placeholder="C:\Images\photo.jpg"
            value={beat.assetPath}
            onChange={(e) => onChange({ assetPath: e.target.value, assetId: null, assetStatus: "unregistered" })}
          />
          <button className="btn btn-secondary" onClick={onRegisterAsset} disabled={beat.assetStatus === "registering"}>
            {beat.assetStatus === "registering" ? <Loader2 size={14} className="spin" /> : "Register"}
          </button>
        </div>
        {beat.assetStatus === "registered" && (
          <div className="vf-asset-status vf-asset-status-ok">
            <CheckCircle2 size={14} /> Asset #{beat.assetId} ready
          </div>
        )}
        {beat.assetStatus === "error" && (
          <div className="vf-asset-status vf-asset-status-error">
            <AlertTriangle size={14} /> {beat.assetError}
          </div>
        )}
      </label>
    </div>
  );
}
