import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Circle,
  Clapperboard,
  DollarSign,
  FileJson,
  Loader2,
  Play,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import {
  cancelStoryRun,
  classifyScenes,
  deleteStory,
  getCompiledProjects,
  getSceneCost,
  getStory,
  listChapters,
  listCharacters,
  listScenes,
  listStoryRuns,
  patchStory,
  produceStory,
  retryStoryRun,
  startStoryRun,
  updateScene,
} from "../api/story";
import { StudioImportModal } from "./StudioImportModal";
import { STORY_RUN_STAGES, VISUAL_MODES, isActiveStoryRun } from "../types/story";
import type {
  CompiledProjectView,
  CostVerdict,
  Story,
  StoryChapter,
  StoryCharacter,
  StoryCost,
  StoryRun,
  StoryScene,
  VisualMode,
} from "../types/story";
import "./StudioPage.css";

const ACTIVE_POLL_MS = 1600;

const STAGE_LABEL: Record<string, string> = {
  STORY_DEVELOPMENT: "Development",
  STORY_BIBLE: "Story bible",
  CHARACTER_BIBLE: "Characters",
  CHAPTER_OUTLINE: "Chapters",
  SCENE_BREAKDOWN: "Scenes",
  SCENE_CLASSIFICATION: "Scene Director + cost",
};

const MODE_BADGE: Record<VisualMode, string> = {
  STILL: "Still",
  STILL_WITH_MOTION: "Still + motion",
  AI_VIDEO: "AI video",
};

export function StudioStoryPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const id = Number(storyId);

  const [story, setStory] = useState<Story | null>(null);
  const [chapters, setChapters] = useState<StoryChapter[]>([]);
  const [scenesByChapter, setScenesByChapter] = useState<Record<number, StoryScene[]>>({});
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [cost, setCost] = useState<StoryCost | null>(null);
  const [runs, setRuns] = useState<StoryRun[]>([]);
  const [compiled, setCompiled] = useState<CompiledProjectView[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const planRun = runs.find((r) => r.scope === "STORY_PLAN") ?? null;
  const produceRun = runs.find((r) => r.scope === "PRODUCE") ?? null;

  const refresh = useCallback(async () => {
    try {
      setLoadError(null);
      const [s, chs, chars, runList] = await Promise.all([
        getStory(id),
        listChapters(id),
        listCharacters(id),
        listStoryRuns(id),
      ]);
      setStory(s);
      setChapters(chs);
      setCharacters(chars);
      setRuns(runList);
      getCompiledProjects(id)
        .then((r) => setCompiled(r.projects))
        .catch(() => setCompiled([]));

      const scenePairs = await Promise.all(chs.map((c) => listScenes(c.id).then((sc) => [c.id, sc] as const)));
      setScenesByChapter(Object.fromEntries(scenePairs));

      if (scenePairs.some(([, sc]) => sc.length > 0)) {
        setCost(await getSceneCost(id).catch(() => null));
      } else {
        setCost(null);
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load this story.");
    } finally {
      setLoaded(true);
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while a run (planning or produce) is active, or a handed-off
  // Factory render is still going; a full refresh once things settle.
  const runActive = runs.some((r) => isActiveStoryRun(r.status));
  const renderActive = compiled.some(
    (p) => p.factory_run != null && !["COMPLETED", "FAILED", "CANCELLED"].includes(p.factory_run.status),
  );
  useEffect(() => {
    if (!runActive && !renderActive) return;
    pollRef.current = setTimeout(async () => {
      try {
        const [runList, comp] = await Promise.all([listStoryRuns(id), getCompiledProjects(id).catch(() => null)]);
        setRuns(runList);
        if (comp) setCompiled(comp.projects);
        if (runActive && !runList.some((r) => isActiveStoryRun(r.status))) refresh();
      } catch {
        /* transient -- keep the last known state */
      }
    }, ACTIVE_POLL_MS);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [runActive, renderActive, id, refresh]);

  if (loadError) {
    return (
      <>
        <PageHeader title="Storytelling Studio" />
        <div className="studio-alert studio-alert-error">{loadError}</div>
      </>
    );
  }
  if (!loaded || !story) {
    return (
      <>
        <PageHeader title="Storytelling Studio" />
        <Loader2 size={20} className="spin" />
      </>
    );
  }

  const totalScenes = Object.values(scenesByChapter).reduce((n, sc) => n + sc.length, 0);

  return (
    <>
      <PageHeader
        title={story.title}
        subtitle={story.logline ?? undefined}
        actions={
          <div className="studio-header-actions">
            <button className="btn btn-secondary" onClick={() => navigate("/studio")}>
              <ArrowLeft size={14} />
              All stories
            </button>
            <button className="btn btn-secondary" disabled={runActive} onClick={() => setImportOpen(true)}>
              <FileJson size={14} />
              Import script
            </button>
            <DeleteStoryButton
              disabled={runActive}
              onDelete={async () => {
                await deleteStory(id);
                navigate("/studio");
              }}
            />
          </div>
        }
      />

      <div className="studio-meta-row">
        <span className="studio-status-pill">{story.mode}</span>
        <span className="studio-status-pill">{story.status}</span>
        <span className="studio-meta-dim">
          {chapters.length} chapter{chapters.length === 1 ? "" : "s"} · {totalScenes} scene
          {totalScenes === 1 ? "" : "s"} · {characters.length} character{characters.length === 1 ? "" : "s"}
        </span>
      </div>

      <RunPanel
        run={planRun}
        story={story}
        onChange={(r) => setRuns((prev) => [r, ...prev.filter((x) => x.id !== r.id)])}
        onSettled={refresh}
      />

      <ProducePanel
        storyId={id}
        story={story}
        planRun={planRun}
        produceRun={produceRun}
        compiled={compiled}
        onChange={(r) => setRuns((prev) => [r, ...prev.filter((x) => x.id !== r.id)])}
      />

      {cost && <CostBar cost={cost} />}

      {characters.length > 0 && (
        <section className="studio-card">
          <h3 className="studio-card-title">Cast</h3>
          <ul className="studio-cast-list">
            {characters.map((c) => (
              <li key={c.id}>
                <strong>{c.name}</strong>
                {c.role ? <span className="studio-meta-dim"> — {c.role}</span> : null}
                {c.canonical_prompt_block ? (
                  <div className="studio-prompt-block">{c.canonical_prompt_block}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      )}

      {chapters.map((chapter) => (
        <ChapterScenes
          key={chapter.id}
          chapter={chapter}
          scenes={scenesByChapter[chapter.id] ?? []}
          onSceneChanged={refresh}
        />
      ))}

      {totalScenes > 0 && (
        <div className="studio-reclassify-row">
          <button
            className="btn btn-secondary"
            onClick={async () => {
              await classifyScenes(id);
              refresh();
            }}
          >
            <RefreshCw size={14} />
            Re-run Scene Director
          </button>
          <span className="studio-meta-dim">Re-scores every scene and refreshes the cost estimate (keeps your manual overrides).</span>
        </div>
      )}

      {importOpen && (
        <StudioImportModal
          storyId={id}
          hasContent={chapters.length > 0 || characters.length > 0}
          onClose={() => setImportOpen(false)}
          onImported={() => {
            setImportOpen(false);
            refresh();
          }}
        />
      )}
    </>
  );
}

// -- Run panel -------------------------------------------------------

function RunPanel({
  run,
  story,
  onChange,
  onSettled,
}: {
  run: StoryRun | null;
  story: Story;
  onChange: (run: StoryRun) => void;
  onSettled: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newBudget, setNewBudget] = useState("");

  async function act(fn: () => Promise<StoryRun>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (run == null || run.status === "CANCELLED" || run.status === "COMPLETED") {
    return (
      <section className="studio-card">
        <div className="studio-run-head">
          <h3 className="studio-card-title">Planning pipeline</h3>
        </div>
        <p className="studio-meta-dim">
          {run?.status === "CANCELLED"
            ? "The last run was cancelled. Start a new one — completed stages are reused."
            : "Runs Development → Story bible → Characters → Chapters → Scenes → Scene Director, then a cost check."}
        </p>
        {error && <div className="studio-alert studio-alert-error">{error}</div>}
        <div className="studio-run-actions">
          <button className="btn btn-primary" disabled={busy} onClick={() => act(() => startStoryRun(story.id))}>
            {busy ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
            Run planning
          </button>
        </div>
      </section>
    );
  }

  const stepper = (
    <ol className="studio-stepper">
      {STORY_RUN_STAGES.map((stage) => {
        const state = stageState(run, stage);
        return (
          <li key={stage} className={`studio-step studio-step--${state}`}>
            {state === "done" ? (
              <CheckCircle2 size={15} />
            ) : state === "active" ? (
              <Loader2 size={15} className="spin" />
            ) : state === "failed" ? (
              <XCircle size={15} />
            ) : (
              <Circle size={15} />
            )}
            <span>{STAGE_LABEL[stage]}</span>
          </li>
        );
      })}
    </ol>
  );

  if (isActiveStoryRun(run.status)) {
    return (
      <section className="studio-card">
        <div className="studio-run-head">
          <h3 className="studio-card-title">
            <Loader2 size={15} className="spin" /> Planning… <span className="studio-meta-dim">attempt {run.attempt}</span>
          </h3>
        </div>
        {stepper}
        {error && <div className="studio-alert studio-alert-error">{error}</div>}
        <div className="studio-run-actions">
          <button className="btn btn-secondary" disabled={busy} onClick={() => act(() => cancelStoryRun(run.id))}>
            {busy ? <Loader2 size={14} className="spin" /> : <Ban size={13} />}
            Cancel
          </button>
        </div>
      </section>
    );
  }

  if (run.status === "READY") {
    return (
      <section className="studio-card studio-card--ok">
        <div className="studio-run-head">
          <h3 className="studio-card-title">
            <CheckCircle2 size={15} /> Plan ready
          </h3>
        </div>
        {stepper}
        <p className="studio-meta-dim">
          Every scene is broken down and classified. Review the Scene Director calls and cost below, then re-run
          the pipeline any time — finished stages are reused.
        </p>
        <div className="studio-run-actions">
          <button className="btn btn-secondary" disabled={busy} onClick={() => act(() => retryStoryRun(run.id))}>
            <RefreshCw size={14} />
            Re-run
          </button>
        </div>
      </section>
    );
  }

  const costBlocked = run.status === "NEEDS_REVIEW" && run.error_code === "COST_GUARD_BLOCKED";

  return (
    <section className={`studio-card ${costBlocked ? "studio-card--warn" : "studio-card--failed"}`}>
      <div className="studio-run-head">
        <h3 className="studio-card-title">
          {costBlocked ? <AlertTriangle size={15} /> : <XCircle size={15} />}
          {costBlocked ? "Paused — over budget" : "Run failed"}
          <span className="studio-meta-dim"> at {STAGE_LABEL[run.failed_stage ?? ""] ?? run.failed_stage}</span>
        </h3>
      </div>
      {stepper}
      {run.error_message && <p className="studio-run-error">{run.error_message}</p>}

      {costBlocked && run.est_cost_json && (
        <div className="studio-budget-fix">
          <div className="studio-meta-dim">
            Estimated ${fmt(run.est_cost_json.total_usd)} vs cap ${fmt(run.est_cost_json.effective_cap_usd)} (
            {run.est_cost_json.cap_source})
          </div>
          <label className="studio-field studio-field--inline">
            <span>New budget cap (USD)</span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={newBudget}
              onChange={(e) => setNewBudget(e.target.value)}
              placeholder={String(story.budget_usd ?? "")}
            />
          </label>
          {run.est_cost_json.cap_source === "cost_guard" && (
            <p className="studio-meta-dim">
              This story's cap comes from its project config's cost guard, not the budget field — raising the budget
              here won't lift it (config editing lands in a later phase).
            </p>
          )}
        </div>
      )}

      {error && <div className="studio-alert studio-alert-error">{error}</div>}
      <div className="studio-run-actions">
        <button
          className="btn btn-primary"
          disabled={busy}
          onClick={async () => {
            if (costBlocked && newBudget.trim()) {
              await patchStory(story.id, { budget_usd: Number(newBudget) });
            }
            act(() => retryStoryRun(run.id));
            onSettled();
          }}
        >
          {busy ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          {costBlocked ? "Raise cap & retry" : "Retry"}
        </button>
      </div>
    </section>
  );
}

type StepState = "done" | "active" | "failed" | "pending";

function stageState(run: StoryRun, stage: string): StepState {
  const order = STORY_RUN_STAGES as readonly string[];
  const stageIdx = order.indexOf(stage);
  if (run.status === "READY" || run.status === "COMPLETED") return "done";
  if (run.status === "FAILED" || run.status === "NEEDS_REVIEW") {
    const failedIdx = order.indexOf(run.failed_stage ?? "");
    if (failedIdx === -1) return "pending";
    if (stageIdx < failedIdx) return "done";
    if (stageIdx === failedIdx) return "failed";
    return "pending";
  }
  const currentIdx = order.indexOf(run.status);
  if (currentIdx === -1) return "pending";
  if (stageIdx < currentIdx) return "done";
  if (stageIdx === currentIdx) return "active";
  return "pending";
}

// -- Produce panel (compile + Factory handoff) ---------------------

const RENDER_DONE = ["COMPLETED", "FAILED", "CANCELLED"];

function ProducePanel({
  storyId,
  story,
  planRun,
  produceRun,
  compiled,
  onChange,
}: {
  storyId: number;
  story: Story;
  planRun: StoryRun | null;
  produceRun: StoryRun | null;
  compiled: CompiledProjectView[];
  onChange: (run: StoryRun) => void;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const planReady = story.status === "SCENES_READY" || planRun?.status === "READY";
  const canProduce = planReady && (produceRun == null || !isActiveStoryRun(produceRun.status));

  async function doProduce() {
    setBusy(true);
    setError(null);
    try {
      onChange(await produceStory(storyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start production.");
    } finally {
      setBusy(false);
    }
  }

  if (!planReady && produceRun == null) return null;

  const produceState =
    produceRun == null
      ? null
      : isActiveStoryRun(produceRun.status)
        ? "active"
        : produceRun.status === "FAILED"
          ? "failed"
          : "done";

  return (
    <section
      className={`studio-card ${produceState === "failed" ? "studio-card--failed" : produceState === "done" ? "studio-card--ok" : ""}`}
    >
      <div className="studio-run-head">
        <h3 className="studio-card-title">
          <Clapperboard size={15} /> Produce
        </h3>
        {produceRun && <span className="studio-status-pill">{produceRun.status}</span>}
      </div>

      {produceState === "active" && (
        <p className="studio-meta-dim">
          {produceRun!.status === "COMPILING"
            ? "Compiling scenes into renderable projects…"
            : "Handing each project to the Video Factory…"}
        </p>
      )}
      {produceState === "failed" && <p className="studio-run-error">{produceRun!.error_message}</p>}
      {produceState == null && (
        <p className="studio-meta-dim">
          Compiles every chapter into a beat plan (one project per chapter, or one for the whole story) and starts a
          Video Factory render for each — character prompt blocks are baked into every scene's image prompt.
        </p>
      )}

      {compiled.length > 0 && (
        <ul className="studio-compiled-list">
          {compiled.map((p) => (
            <li key={p.project_id}>
              <span className="studio-compiled-label">{p.label}</span>
              {p.factory_run ? (
                <span
                  className={`studio-badge ${
                    p.factory_run.status === "COMPLETED"
                      ? "studio-badge--STILL_WITH_MOTION"
                      : p.factory_run.status === "FAILED"
                        ? "studio-badge--AI_VIDEO"
                        : "studio-badge--STILL"
                  }`}
                >
                  {p.factory_run.status}
                  {p.factory_run.failed_stage ? ` · ${p.factory_run.failed_stage}` : ""}
                </span>
              ) : (
                <span className="studio-meta-dim">not started</span>
              )}
              <button className="studio-unlock" onClick={() => navigate("/video-factory")}>
                open in Video Factory
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <div className="studio-alert studio-alert-error">{error}</div>}

      <div className="studio-run-actions">
        <button className="btn btn-primary" disabled={busy || !canProduce} onClick={doProduce}>
          {busy ? <Loader2 size={14} className="spin" /> : <Clapperboard size={14} />}
          {produceRun == null ? "Produce" : "Re-produce"}
        </button>
        {compiled.some((p) => !RENDER_DONE.includes(p.factory_run?.status ?? "")) && produceRun?.status === "COMPLETED" && (
          <span className="studio-meta-dim">Renders run in the background — track them in Video Factory.</span>
        )}
      </div>
    </section>
  );
}

// -- Cost bar -------------------------------------------------------

const VERDICT_CLASS: Record<CostVerdict, string> = {
  OK: "studio-verdict--ok",
  WARN: "studio-verdict--warn",
  BLOCK: "studio-verdict--block",
  UNKNOWN: "studio-verdict--unknown",
};

function CostBar({ cost }: { cost: StoryCost }) {
  const e = cost.estimate;
  return (
    <section className="studio-card">
      <div className="studio-run-head">
        <h3 className="studio-card-title">
          <DollarSign size={15} /> Pre-flight cost
        </h3>
        <span className={`studio-verdict ${VERDICT_CLASS[cost.verdict]}`}>{cost.verdict}</span>
      </div>
      <div className="studio-cost-grid">
        <div>
          <div className="studio-cost-num">${fmt(cost.total_usd)}</div>
          <div className="studio-meta-dim">estimated total</div>
        </div>
        <div>
          <div className="studio-cost-num">${fmt(cost.effective_cap_usd)}</div>
          <div className="studio-meta-dim">cap ({cost.cap_source})</div>
        </div>
        <div>
          <div className="studio-cost-num">
            {num(cost.scene_counts.new_images)} + {num(cost.scene_counts.ai_video_scenes)}
          </div>
          <div className="studio-meta-dim">images + AI-video scenes</div>
        </div>
      </div>
      <div className="studio-cost-breakdown">
        LLM ${fmt(e.llm_usd)} · images ${fmt(e.image_usd)} · video ${fmt(e.video_usd)} · TTS ${fmt(e.tts_usd)} · package $
        {fmt(e.package_usd)}
      </div>
      {cost.notes.length > 0 && (
        <ul className="studio-cost-notes">
          {cost.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

// -- Chapter + scenes --------------------------------------------

function ChapterScenes({
  chapter,
  scenes,
  onSceneChanged,
}: {
  chapter: StoryChapter;
  scenes: StoryScene[];
  onSceneChanged: () => void;
}) {
  return (
    <section className="studio-card">
      <h3 className="studio-card-title">
        {chapter.order}. {chapter.title ?? "Chapter"}
      </h3>
      {chapter.goal && <p className="studio-meta-dim">{chapter.goal}</p>}
      {scenes.length === 0 ? (
        <p className="studio-meta-dim">No scenes yet — run the planning pipeline.</p>
      ) : (
        <div className="studio-table-wrap studio-table-wrap--flush">
          <table className="studio-table studio-scene-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Scene</th>
                <th>Type</th>
                <th>Scores (imp/mov/emo/cplx)</th>
                <th>Visual</th>
                <th>Est.</th>
              </tr>
            </thead>
            <tbody>
              {scenes.map((scene) => (
                <SceneRow key={scene.id} scene={scene} onChanged={onSceneChanged} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SceneRow({ scene, onChanged }: { scene: StoryScene; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);

  async function setMode(mode: VisualMode, source: "AUTO" | "USER") {
    setBusy(true);
    try {
      await updateScene(scene, { visual_mode: mode, visual_mode_source: source });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  const scores = [
    scene.importance_score,
    scene.movement_score,
    scene.emotion_score,
    scene.complexity_score,
  ]
    .map((s) => (s == null ? "–" : s))
    .join(" / ");

  return (
    <tr>
      <td>{scene.order}</td>
      <td>
        <div className="studio-scene-narration">{scene.narration ?? "—"}</div>
        {scene.reuse_asset_from_scene_id != null && (
          <span className="studio-meta-dim">reuses scene #{scene.reuse_asset_from_scene_id}'s image</span>
        )}
      </td>
      <td>{scene.scene_type ?? "—"}</td>
      <td>
        <span className="studio-scores">{scores}</span>
        {scene.composite_score != null && <span className="studio-composite"> → {scene.composite_score}</span>}
      </td>
      <td>
        <div className="studio-visual-cell">
          <span className={`studio-badge studio-badge--${scene.visual_mode}`}>{MODE_BADGE[scene.visual_mode]}</span>
          <select
            value={scene.visual_mode}
            disabled={busy}
            onChange={(e) => setMode(e.target.value as VisualMode, "USER")}
          >
            {VISUAL_MODES.map((m) => (
              <option key={m} value={m}>
                {MODE_BADGE[m]}
              </option>
            ))}
          </select>
          {scene.visual_mode_source === "USER" && (
            <button
              className="studio-unlock"
              disabled={busy}
              title="Hand this scene back to the Scene Director"
              onClick={() => setMode(scene.visual_mode, "AUTO")}
            >
              locked ✕
            </button>
          )}
        </div>
      </td>
      <td>{scene.est_cost_usd == null ? "—" : `$${fmt(scene.est_cost_usd)}`}</td>
    </tr>
  );
}

// -- misc ----------------------------------------------------------

function DeleteStoryButton({ disabled, onDelete }: { disabled: boolean; onDelete: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!confirming) {
    return (
      <button className="btn btn-secondary" disabled={disabled} onClick={() => setConfirming(true)}>
        <Trash2 size={14} />
        Delete
      </button>
    );
  }
  return (
    <button
      className="btn btn-danger"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await onDelete();
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
      Confirm delete
    </button>
  );
}

function fmt(n: number | null | undefined): string {
  return n == null ? "?" : n.toFixed(2);
}
function num(v: number | boolean | undefined): number {
  return typeof v === "number" ? v : 0;
}
