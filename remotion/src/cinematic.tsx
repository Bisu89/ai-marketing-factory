import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ease, rng, useEnter } from "./collage";
import type { PresetProps } from "./presets";
import type { Scene, SceneText } from "./schema";

// "Cinematic" theme: full-bleed paintings with slow camera drift, warm vignette and film grain;
// data scenes on dark parchment with gold type. Same manifest, same presets, different look.
export const CINE = {
  bg: "#0e0c09",
  parchment: "#17130d",
  cream: "#f1e6cc",
  gold: "#d6b068",
  goldDim: "rgba(214,176,104,0.45)",
  goldSoft: "rgba(214,176,104,0.95)",
  red: "#b3402f",
  blue: "#6f93ad",
  serif: '"Times New Roman", "Cambria", "Georgia", serif',
} as const;

const byRole = (s: Scene, ...roles: SceneText["role"][]) => s.texts.filter((t) => roles.includes(t.role));
const firstText = (s: Scene, ...roles: SceneText["role"][]) => byRole(s, ...roles)[0];
const fit = (text: string, base: number, maxChars: number) => Math.round(base * Math.min(1, maxChars / Math.max(text.length, 1)));

function Grain() {
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity: 0.16, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <filter id="cine-grain">
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="11" />
        <feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.35  0 0 0 1.1 -0.2" />
      </filter>
      <rect width="100%" height="100%" filter="url(#cine-grain)" />
    </svg>
  );
}

function Vignette({ strength = 0.62 }: { strength?: number }) {
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 48%, rgba(8,5,2,${strength}) 100%), linear-gradient(to top, rgba(8,5,2,0.78) 0%, rgba(8,5,2,0) 34%)`,
        pointerEvents: "none",
      }}
    />
  );
}

/** Slow drift: direction and focus come from the scene key so the same scene always moves the same way. */
function useDrift(scene: Scene, zoomTo = 1.1) {
  const frame = useCurrentFrame();
  const r = rng(scene.key);
  const t = Math.min(1, frame / Math.max(scene.durationFrames, 1));
  const dir = r() < 0.5 ? -1 : 1;
  const inward = r() < 0.7;
  const scale = inward ? 1 + (zoomTo - 1) * t : zoomTo - (zoomTo - 1) * t;
  return { scale, x: dir * (t - 0.5) * 36, y: (r() - 0.5) * 18 * (t - 0.5) };
}

const FILTER = "sepia(0.14) saturate(0.96) contrast(1.05) brightness(0.93)";

function Painting({ scene, style, fit: mode = "cover" }: { scene: Scene; style?: CSSProperties; fit?: "cover" | "contain" }) {
  if (!scene.imageSrc) return null;
  return <Img src={staticFile(scene.imageSrc)} style={{ width: "100%", height: "100%", objectFit: mode, filter: FILTER, ...style }} />;
}

function Fade({ at, children, style }: { at: number; children: ReactNode; style?: CSSProperties }) {
  const p = useEnter(at, 18);
  return <div style={{ opacity: p, transform: `translateY(${(1 - p) * 18}px)`, ...style }}>{children}</div>;
}

function Credit({ text, at }: { text: string; at: number }) {
  return (
    <Fade at={at} style={{ position: "absolute", left: 90, bottom: 190, fontFamily: CINE.serif, fontStyle: "italic", fontSize: 30, color: CINE.cream, opacity: 0.82, textShadow: "0 2px 8px rgba(0,0,0,0.9)" }}>
      <span style={{ borderLeft: `3px solid ${CINE.gold}`, paddingLeft: 14 }}>{text}</span>
    </Fade>
  );
}

function Frame({ children, dark = CINE.parchment }: { children: ReactNode; dark?: string }) {
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 40%, #241d13 0%, ${dark} 70%)` }}>
      <div style={{ position: "absolute", inset: 46, border: `2px solid ${CINE.goldDim}` }} />
      <div style={{ position: "absolute", inset: 58, border: "1px solid rgba(214,176,104,0.22)" }} />
      {children}
      <Grain />
    </AbsoluteFill>
  );
}

// -- image scenes -----------------------------------------------------------------------------
export function CinePhoto({ scene }: PresetProps) {
  const { scale, x, y } = useDrift(scene);
  const portrait = (scene.imageAspect ?? 2) < 1.3;
  const head = firstText(scene, "headline");
  const cap = firstText(scene, "caption", "label");
  return (
    <AbsoluteFill style={{ background: CINE.bg }}>
      {portrait ? (
        <>
          <AbsoluteFill style={{ transform: "scale(1.25)", filter: "blur(38px) brightness(0.5)" }}>
            <Painting scene={scene} />
          </AbsoluteFill>
          <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px) scale(${scale})` }}>
            <Painting scene={scene} fit="contain" />
          </AbsoluteFill>
        </>
      ) : (
        <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px) scale(${scale})` }}>
          <Painting scene={scene} />
        </AbsoluteFill>
      )}
      <Vignette />
      <Grain />
      {head && (
        <Fade at={head.cueFrame + 6} style={{ position: "absolute", left: 90, bottom: 250, maxWidth: 1300, fontFamily: CINE.serif, fontWeight: 700, fontSize: fit(head.text, 92, 22), color: CINE.cream, textShadow: "0 4px 18px rgba(0,0,0,0.9)" }}>
          {head.text}
        </Fade>
      )}
      {cap && <Credit text={cap.text} at={cap.cueFrame} />}
    </AbsoluteFill>
  );
}

export function CinePortrait({ scene }: PresetProps) {
  const { scale } = useDrift(scene, 1.06);
  const head = firstText(scene, "headline", "caption");
  const date = firstText(scene, "date");
  const label = firstText(scene, "label");
  const enter = useEnter(0, 20);
  return (
    <Frame>
      <div style={{ position: "absolute", left: 170, top: 100, width: 640, height: 880, border: `3px solid ${CINE.gold}`, boxShadow: "0 0 60px rgba(0,0,0,0.8)", overflow: "hidden", opacity: enter }}>
        <div style={{ width: "100%", height: "100%", transform: `scale(${scale})` }}>
          <Painting scene={scene} />
        </div>
      </div>
      {head && (
        <Fade at={head.cueFrame + 8} style={{ position: "absolute", left: 900, top: 300, width: 900, fontFamily: CINE.serif, fontWeight: 700, fontSize: fit(head.text, 120, 14), lineHeight: 1.05, color: CINE.gold }}>
          {head.text}
        </Fade>
      )}
      {date && (
        <Fade at={date.cueFrame} style={{ position: "absolute", left: 904, top: 640, fontFamily: CINE.serif, fontSize: 52, color: CINE.cream }}>
          {date.text}
        </Fade>
      )}
      {label && (
        <Fade at={label.cueFrame} style={{ position: "absolute", left: 904, top: 730, fontFamily: CINE.serif, fontStyle: "italic", fontSize: 38, color: CINE.cream, opacity: 0.85 }}>
          {label.text}
        </Fade>
      )}
    </Frame>
  );
}

export function CineSplit({ scene }: PresetProps) {
  const { scale } = useDrift(scene, 1.06);
  const [a, b] = [scene.texts[0], scene.texts[1]];
  return (
    <Frame>
      <div style={{ position: "absolute", left: 120, top: 120, width: 800, height: 760, border: `3px solid ${CINE.gold}`, overflow: "hidden" }}>
        <div style={{ width: "100%", height: "100%", transform: `scale(${scale})` }}>
          <Painting scene={scene} />
        </div>
      </div>
      {a && (
        <Fade at={Math.max(a.cueFrame, 12)} style={{ position: "absolute", left: 130, top: 905, fontFamily: CINE.serif, fontStyle: "italic", fontSize: 36, color: CINE.cream }}>
          {a.text}
        </Fade>
      )}
      {b && (
        <Fade at={Math.max(b.cueFrame, 24)} style={{ position: "absolute", left: 1010, top: 250, width: 800, fontFamily: CINE.serif, fontWeight: 700, fontSize: fit(b.text, 92, 20), lineHeight: 1.1, color: CINE.gold }}>
          {b.text}
        </Fade>
      )}
    </Frame>
  );
}

// -- data scenes --------------------------------------------------------------------------------
export function CineNumber({ scene }: PresetProps) {
  const frame = useCurrentFrame();
  const num = firstText(scene, "number", "date", "headline");
  const unit = firstText(scene, "label", "caption");
  const plain = num && /^\d{1,12}$/.test(num.text);
  const count = interpolate(frame, [4, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const shown = num ? (plain ? String(Math.round(Number(num.text) * count)) : num.text) : "";
  return (
    <Frame>
      {num && (
        <Fade at={0} style={{ position: "absolute", left: 0, right: 0, top: 250, textAlign: "center", fontFamily: CINE.serif, fontWeight: 700, fontSize: fit(num.text, 340, 8), color: CINE.gold, letterSpacing: "0.02em", textShadow: "0 0 50px rgba(214,176,104,0.25)" }}>
          {shown}
        </Fade>
      )}
      {unit && (
        <Fade at={Math.max(unit.cueFrame, 18)} style={{ position: "absolute", left: 0, right: 0, top: 690, textAlign: "center", fontFamily: CINE.serif, fontStyle: "italic", fontSize: 56, color: CINE.cream }}>
          {unit.text}
        </Fade>
      )}
    </Frame>
  );
}

export function CineTimeline({ scene }: PresetProps) {
  const frame = useCurrentFrame();
  const dates = byRole(scene, "date", "number").slice(0, 5);
  const notes = scene.texts.filter((t) => !dates.includes(t)).slice(0, 2);
  const draw = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp", easing: ease });
  const xs = dates.map((_, i) => (dates.length === 1 ? 960 : 300 + (i * 1320) / (dates.length - 1)));
  return (
    <Frame>
      <div style={{ position: "absolute", left: 160, top: 536, width: 1600 * draw, height: 3, background: CINE.gold }} />
      {dates.map((d, i) => (
        <Fade key={i} at={Math.max(d.cueFrame, 20 + i * 9)} style={{ position: "absolute", left: xs[i] - 200, top: i % 2 === 0 ? 300 : 580, width: 400, textAlign: "center", fontFamily: CINE.serif, fontWeight: 700, fontSize: fit(d.text, 120, 8), color: CINE.gold }}>
          {d.text}
          <div style={{ position: "absolute", left: 188, top: i % 2 === 0 ? 150 : -45, width: 24, height: 24, borderRadius: 24, background: CINE.parchment, border: `4px solid ${CINE.gold}` }} />
        </Fade>
      ))}
      {notes.map((n, i) => (
        <Fade key={`n${i}`} at={Math.max(n.cueFrame, 30)} style={{ position: "absolute", left: 160, bottom: 190 + i * 64, fontFamily: CINE.serif, fontStyle: "italic", fontSize: 40, color: CINE.cream }}>
          {n.text}
        </Fade>
      ))}
    </Frame>
  );
}

export function CineMap({ scene }: PresetProps) {
  const r = rng(scene.key);
  const rings = Array.from({ length: 8 }, (_, i) => {
    const pts = Array.from({ length: 36 }, (_, k) => {
      const a = (k / 36) * Math.PI * 2;
      const w = 1 + (r() - 0.5) * 0.14;
      return `${960 + Math.cos(a) * (120 + i * 110) * w},${540 + Math.sin(a) * (70 + i * 64) * w}`;
    });
    return `M${pts.join("L")}Z`;
  });
  const pin = useEnter(24, 16);
  const place = firstText(scene, "label", "headline", "caption");
  return (
    <Frame>
      <svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {rings.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={CINE.gold} strokeOpacity={0.22} strokeWidth={2} />
        ))}
        <circle cx={1190} cy={500 - (1 - pin) * 60} r={18} fill={CINE.red} stroke={CINE.cream} strokeWidth={4} opacity={pin} />
      </svg>
      {place && (
        <Fade at={place.cueFrame + 8} style={{ position: "absolute", left: 150, bottom: 190, fontFamily: CINE.serif, fontWeight: 700, fontSize: 64, color: CINE.cream }}>
          {place.text}
        </Fade>
      )}
    </Frame>
  );
}

export function CineEvidence({ scene }: PresetProps) {
  const cards = scene.texts.slice(0, 4);
  const stamp = useEnter(40, 10);
  const dim = cards.length === 1 ? { w: 1120, h: 440, font: 70 } : cards.length === 2 ? { w: 780, h: 360, font: 58 } : { w: 760, h: 300, font: 52 };
  const pos: Record<number, { x: number; y: number }[]> = {
    1: [{ x: 400, y: 300 }],
    2: [{ x: 110, y: 340 }, { x: 1030, y: 300 }],
    3: [{ x: 160, y: 160 }, { x: 1000, y: 190 }, { x: 580, y: 560 }],
    4: [{ x: 160, y: 150 }, { x: 1000, y: 180 }, { x: 200, y: 560 }, { x: 1020, y: 590 }],
  };
  const layout = pos[cards.length] ?? pos[4];
  const size = (t: string) => Math.max(26, Math.min(dim.font, Math.floor(Math.sqrt(((dim.w - 100) * (dim.h - 100)) / (Math.max(t.length, 1) * 0.66)))));
  const status = scene.claimStatus;
  return (
    <Frame>
      {cards.map((t, i) => (
        <Fade key={i} at={Math.max(t.cueFrame, i * 9)} style={{ position: "absolute", left: layout[i].x, top: layout[i].y, width: dim.w, height: dim.h, background: "#211a11", border: `2px solid ${CINE.gold}`, boxShadow: "0 12px 40px rgba(0,0,0,0.6)", padding: "46px 50px", boxSizing: "border-box", fontFamily: CINE.serif, fontSize: size(t.text), lineHeight: 1.2, color: CINE.cream }}>
          {t.text}
        </Fade>
      ))}
      {status && status !== "unverified" && (
        <div style={{ position: "absolute", right: 120, bottom: 190, opacity: stamp, transform: `scale(${1.3 - 0.3 * stamp})`, border: `5px solid ${status === "disputed" ? CINE.red : CINE.blue}`, color: status === "disputed" ? CINE.red : CINE.blue, fontFamily: CINE.serif, fontWeight: 700, fontSize: 52, padding: "6px 26px", letterSpacing: "0.08em" }}>
          {status === "disputed" ? "CÒN TRANH CÃI" : "ĐÃ XÁC MINH"}
        </div>
      )}
    </Frame>
  );
}

export function CineHeadline({ scene }: PresetProps) {
  const head = firstText(scene, "headline", "caption", "label", "number", "date");
  const sub = scene.texts.find((t) => t !== head);
  const words = head ? head.text.split(/\s+/).slice(0, 9) : [];
  const size = fit(head?.text ?? "", 150, 22);
  return (
    <Frame>
      <div style={{ position: "absolute", left: 150, right: 150, top: 300, display: "flex", flexWrap: "wrap", gap: "0 28px", justifyContent: "center", fontFamily: CINE.serif, fontWeight: 700, fontSize: size, lineHeight: 1.12, color: CINE.cream }}>
        {words.map((w, i) => (
          <Fade key={i} at={i * 5} style={{ color: i === words.length - 1 ? CINE.gold : CINE.cream }}>
            {w}
          </Fade>
        ))}
      </div>
      {sub && (
        <Fade at={Math.max(sub.cueFrame, 30)} style={{ position: "absolute", left: 0, right: 0, bottom: 200, textAlign: "center", fontFamily: CINE.serif, fontStyle: "italic", fontSize: 48, color: CINE.goldSoft }}>
          {sub.text}
        </Fade>
      )}
    </Frame>
  );
}

export const CINE_COMPONENTS = {
  PhotoKenBurns: CinePhoto,
  ArchivalPortrait: CinePortrait,
  NewspaperStack: CinePhoto,
  SplitComparison: CineSplit,
  MapZoom: CineMap,
  TimelineBuild: CineTimeline,
  BigNumber: CineNumber,
  EvidenceBoard: CineEvidence,
  HeadlineImpact: CineHeadline,
} as const;

export function CineSubtitles({ text }: { text: string }) {
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 60 }}>
      <div style={{ maxWidth: 1500, textAlign: "center", fontFamily: CINE.serif, fontWeight: 700, fontSize: 50, lineHeight: 1.2, color: CINE.cream, textShadow: "0 2px 4px #000, 0 0 14px rgba(0,0,0,0.95), 0 0 30px rgba(0,0,0,0.8)" }}>
        {text}
      </div>
    </AbsoluteFill>
  );
}
