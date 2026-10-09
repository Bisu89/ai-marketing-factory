import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS, MOTION } from "./theme";

// ---- deterministic randomness (same seed => same torn edge, every render) ----
export function hashSeed(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function rng(seed: string): () => number {
  let a = hashSeed(seed) || 1;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A rectangle whose edges are jittered like torn paper, as a CSS polygon(). */
export function tornPolygon(seed: string, jitter = 1.6, steps = 26): string {
  const r = rng(seed);
  const j = () => (r() - 0.5) * 2 * jitter;
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) pts.push(`${(i / steps) * 100 + (i === 0 || i === steps ? 0 : j())}% ${Math.max(0, j() + 0.5)}%`);
  for (let i = 1; i <= steps; i++) pts.push(`${Math.min(100, 100 - Math.abs(j()) * 0.4)}% ${(i / steps) * 100}%`);
  for (let i = steps - 1; i >= 0; i--) pts.push(`${(i / steps) * 100 + (i === 0 ? 0 : j())}% ${Math.min(100, 100 - Math.abs(j()) + 0.5)}%`);
  for (let i = steps - 1; i >= 1; i--) pts.push(`${Math.max(0, Math.abs(j()) * 0.4)}% ${(i / steps) * 100}%`);
  return `polygon(${pts.join(", ")})`;
}

// ---- animation helpers --------------------------------------------------------
export const ease = Easing.bezier(0.22, 1, 0.36, 1);

export function useEnter(delay = 0, frames: number = MOTION.enterFrames): number {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, frames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
}

// ---- surfaces ------------------------------------------------------------------
/** Paper background with a fixed (non-flickering) fibre texture and soft vignette. */
export function PaperBackground({ tint = COLORS.paper }: { tint?: string }) {
  return (
    <AbsoluteFill style={{ background: tint }}>
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity: 0.32, mixBlendMode: "multiply" }}>
        <filter id="paper-fibre">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7" />
          <feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.25  0 0 0 0.9 0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#paper-fibre)" />
      </svg>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(60,40,10,0.28) 100%)" }} />
    </AbsoluteFill>
  );
}

export function Halftone({ color = COLORS.ink, opacity = 0.14, size = 14, style }: { color?: string; opacity?: number; size?: number; style?: CSSProperties }) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        backgroundImage: `radial-gradient(${color} 22%, transparent 24%)`,
        backgroundSize: `${size}px ${size}px`,
        pointerEvents: "none",
        ...style,
      }}
    />
  );
}

export function Tape({ rotate = -6, style }: { rotate?: number; style?: CSSProperties }) {
  return (
    <div
      style={{
        position: "absolute",
        width: 150,
        height: 42,
        background: "rgba(236, 214, 150, 0.72)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
        transform: `rotate(${rotate}deg)`,
        clipPath: "polygon(2% 0, 98% 6%, 100% 50%, 97% 100%, 3% 94%, 0 45%)",
        ...style,
      }}
    />
  );
}

/** A torn sheet. The drop shadow sits on a wrapper because clip-path would cut it. */
export function PaperCard({
  seed,
  children,
  style,
  rotate = 0,
  color = COLORS.paperLight,
  jitter = 1.4,
  padding = 0,
}: {
  seed: string;
  children?: ReactNode;
  style?: CSSProperties;
  rotate?: number;
  color?: string;
  jitter?: number;
  padding?: number;
}) {
  return (
    <div style={{ position: "absolute", filter: `drop-shadow(0 10px 14px ${COLORS.shadow})`, transform: `rotate(${rotate}deg)`, ...style }}>
      <div style={{ width: "100%", height: "100%", background: color, clipPath: tornPolygon(seed, jitter), padding, boxSizing: "border-box", overflow: "hidden", position: "relative" }}>
        {children}
      </div>
    </div>
  );
}

/** Marker highlight that wipes in behind text. */
export function Highlight({ children, delay = 0, color = COLORS.yellow, style }: { children: ReactNode; delay?: number; color?: string; style?: CSSProperties }) {
  const p = useEnter(delay, 12);
  // Inline + a cloned background, so the marker follows every wrapped line instead of
  // covering only the first one.
  return (
    <span
      style={{
        padding: "0 0.14em",
        backgroundImage: `linear-gradient(${color}, ${color})`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "0 82%",
        backgroundSize: `${p * 100}% 66%`,
        WebkitBoxDecorationBreak: "clone",
        boxDecorationBreak: "clone",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/** Red hand-drawn style ring that draws itself (annotation accent). */
export function RedCircle({ x, y, w, h, delay = 0 }: { x: number; y: number; w: number; h: number; delay?: number }) {
  const p = useEnter(delay, 18);
  const len = 2 * Math.PI * ((w + h) / 4) * 1.06;
  return (
    <svg style={{ position: "absolute", left: x, top: y, width: w, height: h, overflow: "visible" }} viewBox={`0 0 ${w} ${h}`}>
      <ellipse cx={w / 2} cy={h / 2} rx={w / 2 - 4} ry={h / 2 - 4} fill="none" stroke={COLORS.red} strokeWidth={6} strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - p)} transform={`rotate(-4 ${w / 2} ${h / 2})`} />
    </svg>
  );
}

export const headlineStyle: CSSProperties = {
  fontFamily: FONTS.display,
  textTransform: "uppercase",
  letterSpacing: "0.01em",
  lineHeight: 1.04,
  color: COLORS.ink,
};
