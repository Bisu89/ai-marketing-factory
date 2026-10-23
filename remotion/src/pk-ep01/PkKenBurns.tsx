import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from "remotion";
import { FallingLeaves, Wind } from "../stickman/weather";
import { ENV } from "./data";
import type { Line } from "./data";

// One picture (or an image-to-video clip) with a slow zoom/pan, light hand-held sway and "living picture" effects.
// Same idea as stickman-video's zs-ep01/KenBurns.tsx + Fx.tsx, trimmed to what Packed Light uses.
// fx tokens (space separated):
//   wind | dust | leaves | fog[:#color,opacity] | flicker | hand | still
//   glow:x,y,r,#color,mode,alpha          warm light spot (mode flicker)
//   breath:x,y,w,h[,amp]                  a region of the picture "breathes" (slow bob + tiny scale)
//   sway:x,y,w,h[,amp]                    a region sways side to side (tarp, hand, head)
//   talk:x,y,w,h,lineIdx                  a mouth opens with the loudness of the shot's n-th voice line
// x/y/w/h are fractions of the frame (centre + size).

const W = 1920;
const H = 1080;

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
  const r = num(tok.a[2], 0.1) * W;
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
  const drift = (f * 0.35) % W;
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

// a soft-edged copy of the picture, moved slightly: reads as breathing / swaying without cutting anything out
const Region: React.FC<{ src: string; kind: string; x: number; y: number; w: number; h: number; amp: number; f: number; seed: number }> = ({ src, kind, x, y, w, h, amp, f, seed }) => {
  const mask = `radial-gradient(ellipse ${w * 50}% ${h * 50}% at ${x * 100}% ${y * 100}%, #000 55%, transparent 100%)`;
  const s = Math.sin((f / 30) * 2 * Math.PI * (kind === "breath" ? 0.27 : 0.2) + seed);
  const tf =
    kind === "breath"
      ? `translateY(${-2 * amp * s}px) scale(${1 + 0.014 * amp * s})`
      : `translateX(${7 * amp * s}px) rotate(${0.4 * amp * s}deg)`;
  return (
    <Img
      src={staticFile(src)}
      style={{
        position: "absolute",
        width: "100%",
        height: "100%",
        objectFit: "cover",
        WebkitMaskImage: mask,
        maskImage: mask,
        transform: tf,
        transformOrigin: `${x * 100}% ${(y + h / 2) * 100}%`,
      }}
    />
  );
};

// mouth that opens with the loudness of the shot's n-th voice line (drawn over the picture's own smile)
const Mouth: React.FC<{ x: number; y: number; w: number; h: number; line?: Line; g: number }> = ({ x, y, w, h, line, g }) => {
  if (!line || g < line.from || g > line.to) return null;
  const open = Math.min(1, (ENV[g] ?? 0) * 1.15);
  if (open < 0.12) return null;
  const hh = Math.max(3, h * H * open);
  return (
    <div
      style={{
        position: "absolute",
        left: x * W - (w * W) / 2,
        top: y * H - hh / 2,
        width: w * W,
        height: hh,
        borderRadius: "50%",
        background: "#3b1214",
        boxShadow: "0 0 0 2px #1a0809",
      }}
    />
  );
};

export const PkKenBurns: React.FC<{
  src: string;
  clip?: string;
  dur: number;
  motion: string;
  fx: string;
  fade?: number;
  seed?: string;
  n?: number;
  from?: number;
  lines?: Line[];
  overlay?: React.ReactNode;
  debug?: boolean;
}> = ({ src, clip, dur, motion, fx, fade = 12, seed = "s", n = 1, from = 0, lines = [], overlay, debug }) => {
  const f = useCurrentFrame();
  const g = from + f;
  const toks = parseFx(fx === "none" ? "" : fx);
  const has = (name: string) => toks.filter((t) => t.name === name);
  const m = MOTION[motion] ?? MOTION.in;
  const t = ease(interpolate(f, [0, dur], [0, 1], clamp));
  const sc = (m[0] + (m[1] - m[0]) * t) * 1.012;
  const amp = has("still").length ? 0 : has("hand").length ? 2.6 : 1.1;
  const dx = amp * (Math.sin(f * 0.043 + n) + 0.5 * Math.sin(f * 0.11 + n * 2));
  const dy = amp * (Math.sin(f * 0.037 + n * 3) + 0.5 * Math.sin(f * 0.09));
  const tx = (m[2] + (m[3] - m[2]) * t) * W + dx;
  const ty = (m[4] + (m[5] - m[4]) * t) * H + dy;
  const o = interpolate(f, [0, fade, dur - fade, dur], [0, 1, 1, 0], clamp);
  const flick = has("flicker").length && !has("glow").length ? 0.08 * Math.max(0, Math.sin(f * 0.37) * Math.sin(f * 0.11 + 1.3)) : 0;
  const dust = has("dust").length > 0;
  const still = !clip; // warps and the mouth overlay only make sense on a still picture
  return (
    <AbsoluteFill style={{ background: "#07090c", opacity: o, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${tx}px, ${ty}px) scale(${sc})`, transformOrigin: "50% 50%" }}>
        {clip ? (
          <OffthreadVideo src={staticFile(clip)} muted style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <Img src={staticFile(src)} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover" }} />
        )}
        {still &&
          toks
            .filter((k) => k.name === "breath" || k.name === "sway")
            .map((k, i) => <Region key={i} src={src} kind={k.name} x={num(k.a[0], 0.5)} y={num(k.a[1], 0.5)} w={num(k.a[2], 0.2)} h={num(k.a[3], 0.2)} amp={num(k.a[4], 1)} f={f} seed={n + i} />)}
        {has("glow").map((k, i) => (
          <Glow key={i} tok={k} f={f} seed={n} />
        ))}
        {still &&
          has("talk").map((k, i) => (
            <Mouth key={i} x={num(k.a[0], 0.5)} y={num(k.a[1], 0.5)} w={num(k.a[2], 0.02)} h={num(k.a[3], 0.02)} line={lines.find((l) => l.idx === num(k.a[4], 0))} g={g} />
          ))}
        {overlay}
        {debug &&
          toks
            .filter((k) => ["breath", "sway", "talk"].includes(k.name))
            .map((k, i) => {
              const w = num(k.a[2], 0.2) * W;
              const h = num(k.a[3], 0.2) * H;
              return (
                <div key={i} style={{ position: "absolute", left: num(k.a[0], 0.5) * W - w / 2, top: num(k.a[1], 0.5) * H - h / 2, width: w, height: h, border: "3px dashed #f0f", color: "#f0f", fontSize: 26 }}>
                  {k.name}
                </div>
              );
            })}
      </AbsoluteFill>
      {has("fog").map((k, i) => (
        <Fog key={i} tok={k} f={f} />
      ))}
      {has("leaves").length > 0 && (
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
          <FallingLeaves f={f} seed={seed} count={14} opacity={0.9} colors={["#b8651b", "#d08a2e", "#8f4a14", "#c9a227"]} />
        </svg>
      )}
      {(has("wind").length > 0 || dust) && (
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
          <Wind f={f} seed={seed} count={dust ? 10 : 16} angle={100} speed={dust ? 5 : 9} opacity={dust ? 0.16 : 0.2} />
        </svg>
      )}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 60%, rgba(0,0,0,0.4) 100%)", pointerEvents: "none" }} />
      {flick > 0 && <AbsoluteFill style={{ background: `rgba(255,220,170,${flick})`, mixBlendMode: "screen", pointerEvents: "none" }} />}
    </AbsoluteFill>
  );
};
