import type { CSSProperties } from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { rng, useEnter } from "./collage";
import type { PresetProps } from "./presets";
import type { Scene, SceneText } from "./schema";

// "Poster" theme: every scene is a full-bleed designed collage poster (the image itself carries the
// cut-outs, newsprint, tape and flat colour -- made by the user from the CSV), animated with a slow
// push + tiny hand-held wobble and drifting paper confetti. Scenes with no image (data cards) become
// a flat colour poster with a big cut-out headline. Same manifest and presets as the other themes.
const POSTER = {
  colors: ["#e8532b", "#f2b632", "#2f7fb5", "#c8302f", "#2e8b6a", "#f1e6cc", "#1d1b1a"],
  paper: "#f6efe0",
  ink: "#16130f",
  sans: 'Impact, "Arial Black", "Arial Narrow", Arial, sans-serif',
  body: "Arial, Helvetica, sans-serif",
} as const;

const textOf = (s: Scene, ...roles: SceneText["role"][]) => s.texts.find((t) => roles.includes(t.role));
const fit = (text: string, base: number, maxChars: number) => Math.round(base * Math.min(1, maxChars / Math.max(text.length, 1)));

/** Deterministic falling paper bits: same scene key => same confetti on every render. */
function Confetti({ scene, count = 22 }: { scene: Scene; count?: number }) {
  const frame = useCurrentFrame();
  const r = rng(scene.key + "-confetti");
  const bits = Array.from({ length: count }, () => ({
    x: r() * 1920,
    y0: r() * 1200 - 100,
    speed: 0.6 + r() * 1.4,
    size: 14 + r() * 30,
    rot0: r() * 360,
    spin: (r() - 0.5) * 3,
    kind: Math.floor(r() * 3),
    color: POSTER.colors[Math.floor(r() * POSTER.colors.length)],
  }));
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      {bits.map((b, i) => {
        const y = ((b.y0 + frame * b.speed) % 1280) - 100;
        const style: CSSProperties = {
          position: "absolute",
          left: b.x,
          top: y,
          width: b.size,
          height: b.kind === 2 ? b.size * 0.35 : b.size,
          background: b.kind === 1 ? "transparent" : b.color,
          transform: `rotate(${b.rot0 + frame * b.spin}deg)`,
          borderRadius: b.kind === 0 ? "50%" : 2,
          clipPath: b.kind === 1 ? "polygon(50% 0, 0 100%, 100% 100%)" : undefined,
          opacity: 0.85,
        };
        return b.kind === 1 ? (
          <div key={i} style={{ ...style, background: b.color }} />
        ) : (
          <div key={i} style={style} />
        );
      })}
    </AbsoluteFill>
  );
}

/** Slow push plus a tiny seeded wobble, so a still poster feels hand-held. */
function useMove(scene: Scene) {
  const frame = useCurrentFrame();
  const r = rng(scene.key + "-move");
  const t = Math.min(1, frame / Math.max(scene.durationFrames, 1));
  const phase = r() * 6.28;
  return {
    scale: 1.02 + 0.07 * t,
    x: Math.sin(frame / 38 + phase) * 8,
    y: Math.cos(frame / 47 + phase) * 6,
    rot: Math.sin(frame / 55 + phase) * 0.45,
  };
}

function CutHeadline({ text, at, rot = -2, center = false }: { text: string; at: number; rot?: number; center?: boolean }) {
  const p = useEnter(at, 10);
  const size = center ? Math.max(66, fit(text, 120, 26)) : fit(text, 150, 14);
  return (
    <div
      style={{
        position: "absolute",
        left: 90,
        right: 90,
        ...(center ? { top: 0, bottom: 120 } : { top: 110 }),
        display: "flex",
        alignItems: center ? "center" : undefined,
        justifyContent: "center",
        transform: `rotate(${rot}deg) scale(${0.6 + 0.4 * p})`,
        opacity: p,
      }}
    >
      <span
        style={{
          fontFamily: POSTER.sans,
          fontSize: size,
          lineHeight: 1.02,
          textTransform: "uppercase",
          color: POSTER.ink,
          background: POSTER.paper,
          padding: "10px 34px",
          boxShadow: "8px 10px 0 rgba(0,0,0,0.35)",
          textAlign: "center",
        }}
      >
        {text}
      </span>
    </div>
  );
}

function SmallTag({ text, at }: { text: string; at: number }) {
  const p = useEnter(at, 12);
  return (
    <div
      style={{
        position: "absolute",
        left: 70,
        bottom: 200,
        transform: `rotate(-3deg) translateY(${(1 - p) * 16}px)`,
        opacity: p,
        fontFamily: POSTER.body,
        fontWeight: 700,
        fontSize: 28,
        color: POSTER.ink,
        background: POSTER.paper,
        padding: "6px 16px",
        boxShadow: "4px 5px 0 rgba(0,0,0,0.3)",
      }}
    >
      {text}
    </div>
  );
}

export function PosterScene({ scene }: PresetProps) {
  const m = useMove(scene);
  const head = textOf(scene, "headline", "number", "date");
  const tags = scene.texts.filter((t) => t.role === "caption" || t.role === "label");
  const flat = POSTER.colors[Math.floor(rng(scene.key + "-bg")() * 5)];
  return (
    <AbsoluteFill style={{ background: flat, overflow: "hidden" }}>
      {scene.imageSrc ? (
        <AbsoluteFill style={{ transform: `translate(${m.x}px, ${m.y}px) scale(${m.scale}) rotate(${m.rot}deg)` }}>
          <Img src={staticFile(scene.imageSrc)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </AbsoluteFill>
      ) : (
        <AbsoluteFill style={{ background: `radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18), rgba(0,0,0,0.18))` }} />
      )}
      <Confetti scene={scene} count={scene.imageSrc ? 14 : 30} />
      {scene.imageSrc && head && <CutHeadline text={head.text} at={head.cueFrame} />}
      {!scene.imageSrc && (head ?? tags[0]) && <CutHeadline text={(head ?? tags[0]).text} at={(head ?? tags[0]).cueFrame} center />}
      {scene.imageSrc && tags.map((t) => <SmallTag key={t.text} text={t.text} at={t.cueFrame} />)}
    </AbsoluteFill>
  );
}

export const POSTER_COMPONENTS = {
  PhotoKenBurns: PosterScene,
  ArchivalPortrait: PosterScene,
  NewspaperStack: PosterScene,
  SplitComparison: PosterScene,
  MapZoom: PosterScene,
  TimelineBuild: PosterScene,
  BigNumber: PosterScene,
  EvidenceBoard: PosterScene,
  HeadlineImpact: PosterScene,
} as const;

export function PosterSubtitles({ text }: { text: string }) {
  const stroke = "#000";
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 56 }}>
      <div
        style={{
          maxWidth: 1560,
          textAlign: "center",
          fontFamily: POSTER.body,
          fontWeight: 800,
          fontSize: 52,
          lineHeight: 1.18,
          color: "#fff",
          textShadow: `-3px -3px 0 ${stroke}, 3px -3px 0 ${stroke}, -3px 3px 0 ${stroke}, 3px 3px 0 ${stroke}, 0 4px 10px rgba(0,0,0,0.8)`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
}

