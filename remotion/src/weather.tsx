// Continuous ambient particle effects (snow, rain, wind, embers): ported from a sibling Remotion
// skill (`stickman-video/assets/engine/weather.tsx`, read manually -- not imported, no cross-repo
// dependency). See docs/documentary/PORTING_NOTES.md part C.
//
// Unlike a one-shot cue, every particle here is placed purely from a seeded random plus the current
// frame (no "start" frame to wait for), and wraps around, so a scene can start or end at any point
// in the loop without a visible pop -- exactly what an "optional layer over whatever's already in
// the scene" needs.
//
// Palette note: the original imports a `COL` palette with `ink/orange/yellow/...`. Vox's own
// `theme.ts` has `COLORS` with `ink/yellow/red/blue` but no `orange` -- substituted `COLORS.red`
// for `COL.orange` below so the whole app draws from one palette source.
import { AbsoluteFill, random, useCurrentFrame } from "remotion";
import { COLORS } from "./theme";
import type { AMBIENT_KINDS } from "./schema";

const rad = (d: number) => (d * Math.PI) / 180;
const dir = (a: number) => [Math.sin(rad(a)), Math.cos(rad(a))] as const; // 0 = down, 90 = right
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

// ambient blowing wind/dust: softer and continuously looped
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

// tumbling, swaying leaves (autumn palette by default) -- ported but not wired to any ambient enum
// value yet; kept available for a future preset (see PORTING_NOTES.md part C).
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
            <path d={`M0,${-s} Q${s * 0.8},0 0,${s} Q${-s * 0.8},0 0,${-s} Z`} fill={color} stroke={COLORS.ink} strokeWidth={2} strokeLinejoin="round" />
            <line x1={0} y1={-s} x2={0} y2={s} stroke="rgba(0,0,0,0.3)" strokeWidth={1.5} />
          </g>
        );
      })}
    </g>
  );
};

// a flowing stream: wavy highlight lines whose dashes slide in the flow direction -- ported but not
// wired to any ambient enum value yet (see PORTING_NOTES.md part C).
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

// flying sparks/embers from a point; each particle loops on its own phase
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
      // substituted COLORS.red for the original palette's `orange` (not in Vox's theme -- see file header)
      return <line key={i} x1={qx} y1={qy} x2={px} y2={py} stroke={i % 2 ? COLORS.yellow : COLORS.red} strokeWidth={(2 + r2 * 2) * size} strokeLinecap="round" opacity={1 - t / life} />;
    })}
  </g>
);

// ---- the piece actually wired into Documentary.tsx -------------------------------------------
export type AmbientKind = (typeof AMBIENT_KINDS)[number];

/** Full-bleed, non-interactive particle layer for one of the 4 scene-level `ambient` values.
 * Mounted once per scene (see Documentary.tsx's SceneView), drawn over whatever preset is already
 * showing. Renders nothing for `null`/`undefined` -- existing scenes are unaffected. */
export function AmbientOverlay({ kind, seed }: { kind: AmbientKind; seed: string }) {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {kind === "snow" && <Snowfall f={frame} seed={seed} />}
        {kind === "rain" && <Rain f={frame} seed={seed} />}
        {kind === "wind" && <Wind f={frame} seed={seed} />}
        {kind === "embers" && <Sparks f={frame} x={960} y={1080} seed={seed} count={44} spread={150} speed={8} gravity={0.15} life={90} />}
      </svg>
    </AbsoluteFill>
  );
}
