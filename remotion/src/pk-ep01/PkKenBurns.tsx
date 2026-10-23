import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Wind } from "../stickman/weather";

// One picture with a slow zoom/pan, light hand-held sway and gentle "living picture" effects.
// Same idea as stickman-video's zs-ep01/KenBurns.tsx, trimmed to what Packed Light uses.
// fx tokens (space separated): wind | dust | fog[:#color,opacity] | flicker | glow:x,y,r,#color,mode,alpha | hand | still

// [scale0, scale1, x0, x1, y0, y1] (x/y as a fraction of the frame)
const MOTION: Record<string, number[]> = {
  in: [1.0, 1.12, 0, 0, 0, 0],
  out: [1.14, 1.0, 0, 0, 0, 0],
  "in-left": [1.06, 1.15, 0.02, -0.02, 0, 0],
  "in-right": [1.06, 1.15, -0.02, 0.02, 0, 0],
  "out-left": [1.15, 1.06, 0.02, -0.01, 0, 0],
  "out-right": [1.15, 1.06, -0.02, 0.01, 0, 0],
  "in-up": [1.04, 1.14, 0, 0, 0.02, -0.02],
  "in-down": [1.04, 1.14, 0, 0, -0.02, 0.02],
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = (t: number) => t * t * (3 - 2 * t);

type Tok = { name: string; a: string[] };
const parseFx = (s: string): Tok[] =>
  s
    .split(/\s+/)
    .filter(Boolean)
    .map((t) => {
      const [name, rest] = t.split(/:(.*)/s);
      return { name, a: rest ? rest.split(",") : [] };
    });
const num = (v: string | undefined, d: number) => (v === undefined || v === "" || isNaN(+v) ? d : +v);

const Glow: React.FC<{ tok: Tok; f: number; seed: number }> = ({ tok, f, seed }) => {
  const x = num(tok.a[0], 0.5) * 100;
  const y = num(tok.a[1], 0.5) * 100;
  const r = num(tok.a[2], 0.1) * 1920;
  const color = tok.a[3] || "#ffcf7a";
  const mode = tok.a[4] || "flicker";
  const alpha = num(tok.a[5], 0.7);
  const wob = mode === "flicker" ? 0.7 + 0.2 * Math.sin(f * 0.37 + seed) + 0.1 * Math.sin(f * 1.1 + seed * 2) : 1;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at ${x}% ${y}%, ${color} 0px, rgba(255,160,60,0.35) ${r * 0.35}px, rgba(255,160,60,0) ${r}px)`,
        opacity: alpha * wob,
        mixBlendMode: "screen",
        pointerEvents: "none",
      }}
    />
  );
};

const Fog: React.FC<{ tok: Tok; f: number }> = ({ tok, f }) => {
  const color = tok.a[0] || "#cfd3d8";
  const op = num(tok.a[1], 0.22);
  const drift = (f * 0.35) % 1920;
  const blob = (x: number, y: number, w: number, h: number): React.CSSProperties => ({
    position: "absolute",
    left: x,
    top: y,
    width: w,
    height: h,
    background: `radial-gradient(ellipse at center, ${color} 0%, rgba(255,255,255,0) 70%)`,
    opacity: op,
    filter: "blur(30px)",
  });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div style={blob(-300 + drift * 0.6, 520, 1100, 420)} />
      <div style={blob(900 - drift * 0.4, 600, 1200, 380)} />
      <div style={blob(-900 + drift, 380, 1000, 360)} />
    </AbsoluteFill>
  );
};

export const PkKenBurns: React.FC<{
  src: string;
  dur: number;
  motion: string;
  fx: string;
  fade?: number;
  seed?: string;
  n?: number;
  overlay?: React.ReactNode;
}> = ({ src, dur, motion, fx, fade = 12, seed = "s", n = 1, overlay }) => {
  const f = useCurrentFrame();
  const toks = parseFx(fx === "none" ? "" : fx);
  const has = (name: string) => toks.filter((t) => t.name === name);
  const m = MOTION[motion] ?? MOTION.in;
  const t = ease(interpolate(f, [0, dur], [0, 1], clamp));
  const sc = (m[0] + (m[1] - m[0]) * t) * 1.012;
  const amp = has("still").length ? 0 : has("hand").length ? 2.6 : 1.1;
  const dx = amp * (Math.sin(f * 0.043 + n) + 0.5 * Math.sin(f * 0.11 + n * 2));
  const dy = amp * (Math.sin(f * 0.037 + n * 3) + 0.5 * Math.sin(f * 0.09));
  const tx = (m[2] + (m[3] - m[2]) * t) * 1920 + dx;
  const ty = (m[4] + (m[5] - m[4]) * t) * 1080 + dy;
  const o = interpolate(f, [0, fade, dur - fade, dur], [0, 1, 1, 0], clamp);
  const flick = has("flicker").length && !has("glow").length ? 0.08 * Math.max(0, Math.sin(f * 0.37) * Math.sin(f * 0.11 + 1.3)) : 0;
  const dust = has("dust").length > 0;
  return (
    <AbsoluteFill style={{ background: "#07090c", opacity: o, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${tx}px, ${ty}px) scale(${sc})`, transformOrigin: "50% 50%" }}>
        <Img src={staticFile(src)} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover" }} />
        {has("glow").map((g, i) => (
          <Glow key={i} tok={g} f={f} seed={n} />
        ))}
        {overlay}
      </AbsoluteFill>
      {has("fog").map((g, i) => (
        <Fog key={i} tok={g} f={f} />
      ))}
      {(has("wind").length > 0 || dust) && (
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
          <Wind f={f} seed={seed} count={dust ? 10 : 16} angle={100} speed={dust ? 5 : 9} opacity={dust ? 0.16 : 0.2} />
        </svg>
      )}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.4) 100%)", pointerEvents: "none" }} />
      {flick > 0 && <AbsoluteFill style={{ background: `rgba(255,220,170,${flick})`, mixBlendMode: "screen", pointerEvents: "none" }} />}
    </AbsoluteFill>
  );
};
