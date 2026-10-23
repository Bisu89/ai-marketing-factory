import React from "react";
import { random } from "remotion";
import { COL } from "./fx";

// Continuous ambient effects (snow, fire, wind): unlike fx.tsx's one-shot Burst/Dust,
// these read correctly from any local frame 0 — every particle is placed from a seeded
// random and a frame-driven position, with no "at" trigger frame, and wraps around so a
// scene can start or end at any point without a pop.

const rad = (d: number) => (d * Math.PI) / 180;
const dir = (a: number) => [Math.sin(rad(a)), Math.cos(rad(a))] as const; // 0 = down, 90 = right (same convention as stick.tsx)
const wrap = (v: number, n: number) => ((v % n) + n) % n;

export type Area = { x: number; y: number; w: number; h: number };
const FULL: Area = { x: 0, y: 0, w: 1920, h: 1080 };

// falling snow; angle 0 = straight down, lean it (e.g. 15-25) for a blizzard
export const Snowfall: React.FC<{
  f: number;
  seed?: string;
  count?: number;
  area?: Area;
  angle?: number;
  speed?: number; // px/frame of the fastest (closest) flakes
  size?: [number, number];
  color?: string;
  opacity?: number;
}> = ({ f, seed = "snow", count = 90, area = FULL, angle = 6, speed = 5, size = [2, 6], color = "#fff", opacity = 0.85 }) => {
  const [dx, dy] = dir(angle);
  const padX = area.w * 0.15 + 60;
  const padY = 40;
  const spanX = area.w + padX * 2;
  const spanY = area.h + padY * 2;
  return (
    <g opacity={opacity}>
      {Array.from({ length: count }).map((_, i) => {
        const r0 = random(`${seed}-y${i}`);
        const r1 = random(`${seed}-x${i}`);
        const r2 = random(`${seed}-s${i}`);
        const r3 = random(`${seed}-v${i}`);
        const r4 = random(`${seed}-ph${i}`);
        const v = 0.55 + r3 * 0.9; // depth: slower flakes read as further away
        const rr = size[0] + (size[1] - size[0]) * r2;
        const y = area.y - padY + wrap(f * speed * v * dy + r0 * spanY, spanY);
        const bx = area.x - padX + wrap(f * speed * v * dx + r1 * spanX, spanX);
        const x = bx + Math.sin(f * 0.04 + r4 * 20) * 8; // gentle flutter
        return <circle key={i} cx={x} cy={y} r={rr} fill={color} opacity={0.35 + v * 0.5} />;
      })}
    </g>
  );
};

// stylised flame with layered flicker + rising embers; anchor (x,y) is the base of the fire
export const Fire: React.FC<{
  f: number;
  x: number;
  y: number;
  s?: number; // scale: 1 ≈ 95px tall
  seed?: string;
  embers?: boolean;
}> = ({ f, x, y, s = 1, seed = "fire", embers = true }) => {
  const flicker = (sd: number) => 0.85 + 0.1 * Math.sin(f * 0.5 + sd) + 0.05 * Math.sin(f * 1.3 + sd * 2.3);
  const tongue = (dxBase: number, hBase: number, wBase: number, sd: number, color: string, op: number) => {
    const k = flicker(sd);
    const h = hBase * k * s;
    const w = wBase * (0.9 + 0.1 * Math.sin(f * 0.7 + sd)) * s;
    const bx = x + dxBase * s + Math.sin(f * 0.15 + sd) * 6 * s;
    return (
      <path
        d={`M${bx - w / 2},${y} Q${bx - w * 0.6},${y - h * 0.5} ${bx},${y - h} Q${bx + w * 0.6},${y - h * 0.5} ${bx + w / 2},${y} Z`}
        fill={color}
        opacity={op}
      />
    );
  };
  return (
    <g>
      {tongue(0, 95, 46, 1, COL.red, 0.95)}
      {tongue(-12, 70, 32, 3, COL.orange, 0.95)}
      {tongue(14, 78, 30, 5, COL.orange, 0.9)}
      {tongue(0, 44, 18, 7, COL.yellow, 0.95)}
      {embers &&
        Array.from({ length: 6 }).map((_, i) => {
          const r0 = random(`${seed}-ey${i}`);
          const r1 = random(`${seed}-ex${i}`);
          const r2 = random(`${seed}-es${i}`);
          const period = 90;
          const t = wrap(f * (1.2 + r2 * 0.8) + r0 * period, period) / period;
          const ey = y - 40 * s - 160 * s * t;
          const ex = x + (r1 - 0.5) * 60 * s + Math.sin(f * 0.1 + r1 * 10) * 10;
          return <circle key={i} cx={ex} cy={ey} r={(2.5 + r2 * 2) * s} fill={COL.yellow} opacity={(1 - t) * 0.9} />;
        })}
    </g>
  );
};

// ambient blowing wind/dust: softer and continuously looped, unlike fx.tsx's one-shot SpeedLines
export const Wind: React.FC<{
  f: number;
  seed?: string;
  count?: number;
  area?: Area;
  angle?: number; // direction of travel (dir() convention: 90 = rightwards)
  speed?: number;
  color?: string;
  opacity?: number;
}> = ({ f, seed = "wind", count = 14, area = FULL, angle = 100, speed = 10, color = "#d8d4c8", opacity = 0.35 }) => {
  const [dx, dy] = dir(angle);
  const pad = 160;
  const spanX = area.w + pad * 2;
  return (
    <g opacity={opacity}>
      {Array.from({ length: count }).map((_, i) => {
        const r0 = random(`${seed}-x${i}`);
        const r1 = random(`${seed}-y${i}`);
        const r2 = random(`${seed}-l${i}`);
        const r3 = random(`${seed}-v${i}`);
        const r4 = random(`${seed}-w${i}`);
        const v = 0.6 + r3 * 0.8;
        const len = 120 + r2 * 260;
        const cx = area.x - pad + wrap(f * speed * v * dx + r0 * spanX, spanX);
        const cy = area.y + r1 * area.h + Math.sin(f * 0.03 + r4 * 10) * 14 + wrap(f * speed * v * dy, area.h);
        const x1 = cx - (dx * len) / 2;
        const y1 = cy - (dy * len) / 2;
        const x2 = cx + (dx * len) / 2;
        const y2 = cy + (dy * len) / 2;
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={2 + r4 * 3} strokeLinecap="round" opacity={0.4 + v * 0.5} />;
      })}
    </g>
  );
};

// slanted rain streaks; give `ground` (a y) to add splash rings where drops land
export const Rain: React.FC<{
  f: number;
  seed?: string;
  count?: number;
  area?: Area;
  angle?: number;
  speed?: number;
  len?: [number, number];
  color?: string;
  opacity?: number;
  ground?: number;
}> = ({ f, seed = "rain", count = 160, area = FULL, angle = 12, speed = 28, len = [26, 56], color = "#6f8fb0", opacity = 0.8, ground }) => {
  const [dx, dy] = dir(angle);
  const padX = area.w * 0.2 + 80;
  const padY = 80;
  const spanX = area.w + padX * 2;
  const spanY = area.h + padY * 2;
  return (
    <g opacity={opacity}>
      {Array.from({ length: count }).map((_, i) => {
        const r0 = random(`${seed}-y${i}`);
        const r1 = random(`${seed}-x${i}`);
        const r2 = random(`${seed}-l${i}`);
        const r3 = random(`${seed}-v${i}`);
        const v = 0.7 + r3 * 0.6;
        const l = len[0] + (len[1] - len[0]) * r2;
        const y = area.y - padY + wrap(f * speed * v * dy + r0 * spanY, spanY);
        const x = area.x - padX + wrap(f * speed * v * dx + r1 * spanX, spanX);
        return <line key={i} x1={x} y1={y} x2={x - dx * l} y2={y - dy * l} stroke={color} strokeWidth={1.5 + v * 1.5} strokeLinecap="round" opacity={0.35 + v * 0.5} />;
      })}
      {ground !== undefined &&
        Array.from({ length: Math.round(count / 6) }).map((_, i) => {
          const r0 = random(`${seed}-sp${i}`);
          const r1 = random(`${seed}-sx${i}`);
          const t = wrap(f + r0 * 14, 14) / 14;
          return <ellipse key={i} cx={area.x + r1 * area.w} cy={ground} rx={4 + 12 * t} ry={1.5 + 4 * t} fill="none" stroke={color} strokeWidth={2} opacity={1 - t} />;
        })}
    </g>
  );
};

// tumbling, swaying leaves (autumn palette by default)
export const FallingLeaves: React.FC<{
  f: number;
  seed?: string;
  count?: number;
  area?: Area;
  speed?: number;
  wind?: number;
  size?: [number, number];
  colors?: string[];
  opacity?: number;
}> = ({ f, seed = "leaf", count = 14, area = FULL, speed = 2.4, wind = 1.4, size = [14, 26], colors = ["#c8501e", "#e0a526", "#8a5a2b", "#b33a2e"], opacity = 1 }) => {
  const padX = 120;
  const padY = 60;
  const spanX = area.w + padX * 2;
  const spanY = area.h + padY * 2;
  return (
    <g opacity={opacity}>
      {Array.from({ length: count }).map((_, i) => {
        const r0 = random(`${seed}-y${i}`);
        const r1 = random(`${seed}-x${i}`);
        const r2 = random(`${seed}-s${i}`);
        const r3 = random(`${seed}-v${i}`);
        const r4 = random(`${seed}-sw${i}`);
        const r5 = random(`${seed}-c${i}`);
        const v = 0.6 + r3 * 0.8;
        const s = size[0] + (size[1] - size[0]) * r2;
        const y = area.y - padY + wrap(f * speed * v + r0 * spanY, spanY);
        const x = area.x - padX + wrap(f * wind * v + r1 * spanX, spanX) + Math.sin(f * 0.05 * (0.7 + r4) + r4 * 20) * 40;
        const rot = Math.sin(f * 0.045 * (0.6 + r4) + r4 * 9) * 70 + r4 * 90;
        const color = colors[Math.floor(r5 * colors.length) % colors.length];
        return (
          <g key={i} transform={`translate(${x} ${y}) rotate(${rot})`}>
            <path d={`M0,${-s} Q${s * 0.8},0 0,${s} Q${-s * 0.8},0 0,${-s} Z`} fill={color} stroke={COL.ink} strokeWidth={2} strokeLinejoin="round" />
            <line x1={0} y1={-s} x2={0} y2={s} stroke="rgba(0,0,0,0.3)" strokeWidth={1.5} />
          </g>
        );
      })}
    </g>
  );
};

// a flowing stream: wavy highlight lines whose dashes slide in the flow direction
export const Water: React.FC<{
  f: number;
  area?: Area;
  color?: string;
  speed?: number;
  flow?: 1 | -1; // 1 = flows right
  lines?: number;
  opacity?: number;
}> = ({ f, area = { x: 0, y: 880, w: 1920, h: 200 }, color = "#4aa3d8", speed = 3, flow = 1, lines = 7, opacity = 0.9 }) => {
  const step = 16;
  return (
    <g opacity={opacity}>
      <rect x={area.x} y={area.y} width={area.w} height={area.h} fill={color} opacity={0.7} />
      {Array.from({ length: lines }).map((_, i) => {
        const yy = area.y + ((i + 0.5) / lines) * area.h;
        const amp = 4 + (i % 3) * 2;
        let d = "";
        for (let x = 0; x <= area.w; x += step) {
          const y = yy + Math.sin(x * 0.018 + i * 1.7 - flow * f * 0.08 * speed) * amp;
          d += `${x === 0 ? "M" : "L"}${area.x + x},${y} `;
        }
        return (
          <path
            key={i}
            d={d}
            fill="none"
            stroke="#fff"
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={`${40 + (i % 3) * 20} ${70 + (i % 2) * 30}`}
            strokeDashoffset={-flow * f * speed * 2 - i * 37}
            opacity={0.55}
          />
        );
      })}
    </g>
  );
};

// flying sparks from a point (forge, clash, campfire); each particle loops on its own phase
export const Sparks: React.FC<{
  f: number;
  x: number;
  y: number;
  seed?: string;
  count?: number;
  spread?: number; // cone width in degrees around straight up
  speed?: number;
  gravity?: number;
  life?: number;
  size?: number;
}> = ({ f, x, y, seed = "spark", count = 30, spread = 80, speed = 12, gravity = 0.4, life = 38, size = 1 }) => (
  <g>
    {Array.from({ length: count }).map((_, i) => {
      const r0 = random(`${seed}-p${i}`);
      const r1 = random(`${seed}-a${i}`);
      const r2 = random(`${seed}-s${i}`);
      const a = rad(-90 + (r1 - 0.5) * spread);
      const sp = speed * (0.5 + r2 * 0.8);
      const pos = (t: number): [number, number] => [x + Math.cos(a) * sp * t, y + Math.sin(a) * sp * t + 0.5 * gravity * t * t];
      const t = wrap(f + r0 * life, life);
      const [px, py] = pos(t);
      const [qx, qy] = pos(Math.max(0, t - 1.5));
      return <line key={i} x1={qx} y1={qy} x2={px} y2={py} stroke={i % 2 ? COL.yellow : COL.orange} strokeWidth={(2 + r2 * 2) * size} strokeLinecap="round" opacity={1 - t / life} />;
    })}
  </g>
);

// a volley of arrows lobbed along an arc from one point to another (longbow barrage)
export const ArrowVolley: React.FC<{
  f: number;
  from: { x: number; y: number };
  to: { x: number; y: number };
  seed?: string;
  count?: number;
  life?: number; // flight time in frames
  arc?: number; // arc height in px
  spread?: number; // landing scatter in px
  color?: string;
  at?: number; // one-shot mode: all arrows leave at this frame (within `stagger` frames) and fly once; omit for the continuous barrage
  stagger?: number; // one-shot mode: frames over which the launches are spread
}> = ({ f, from, to, seed = "arrow", count = 28, life = 46, arc = 260, spread = 90, color = COL.ink, at, stagger = 6 }) => (
  <g>
    {Array.from({ length: count }).map((_, i) => {
      const r0 = random(`${seed}-p${i}`);
      const r1 = random(`${seed}-j${i}`);
      const r2 = random(`${seed}-a${i}`);
      const t = at === undefined ? wrap(f + r0 * life, life) / life : (f - at - r0 * stagger) / life;
      if (at !== undefined && (t < 0 || t > 1)) return null;
      const h = arc * (0.8 + r2 * 0.4);
      const tx = to.x + (r1 - 0.5) * spread;
      const ty = to.y + (r2 - 0.5) * spread * 0.3;
      const sx = from.x + (r1 - 0.5) * 40;
      const x = sx + (tx - sx) * t;
      const y = from.y + (ty - from.y) * t - 4 * h * t * (1 - t);
      const vx = tx - sx;
      const vy = ty - from.y - 4 * h * (1 - 2 * t);
      const n = Math.hypot(vx, vy) || 1;
      const ux = vx / n;
      const uy = vy / n;
      return (
        <g key={i} opacity={t < 0.06 ? t / 0.06 : t > 0.94 ? (1 - t) / 0.06 : 1}>
          <line x1={x - ux * 38} y1={y - uy * 38} x2={x} y2={y} stroke={color} strokeWidth={3} strokeLinecap="round" />
          <polygon points={`${x},${y} ${x - ux * 9 - uy * 4},${y - uy * 9 + ux * 4} ${x - ux * 9 + uy * 4},${y - uy * 9 - ux * 4}`} fill={color} />
        </g>
      );
    })}
  </g>
);
