import React from "react";
import { random } from "remotion";
import { COL } from "./fx";

// Cheap stickmen for armies: each soldier is a handful of SVG elements, placed deterministically.
// Intended for STATIC layers (render a composition to PNG once with `npx remotion still`, then use the
// image as a parallax layer) with only a few detailed Hero/Actor characters animated on top.

export type Gear = "bow" | "spear" | "sword" | "none";

export const Soldier: React.FC<{
  x: number; // feet (or saddle when mounted)
  y: number;
  s?: number;
  facing?: 1 | -1;
  gear?: Gear;
  patch?: string; // tabard colour
  plume?: string; // helmet crest colour
  mounted?: boolean; // no legs: use on top of a Horse's saddle
}> = ({ x, y, s = 1, facing = 1, gear = "none", patch = "#c0392b", plume, mounted }) => {
  const f = facing;
  const hip = mounted ? y : y - 38 * s;
  const sw = Math.max(1.3, 3.6 * s);
  let d = `M${x},${hip} L${x},${hip - 34 * s} M${x - 9 * s},${hip - 14 * s} L${x},${hip - 28 * s} L${x + f * 11 * s},${hip - 22 * s}`;
  if (!mounted) d += ` M${x - 8 * s},${y} L${x},${hip} L${x + 8 * s},${y}`;
  if (gear === "spear") d += ` M${x + f * 13 * s},${hip + 22 * s} L${x + f * 13 * s},${hip - 100 * s}`;
  if (gear === "sword") d += ` M${x + f * 11 * s},${hip - 22 * s} L${x + f * 30 * s},${hip - 46 * s}`;
  if (gear === "bow") d += ` M${x + f * 17 * s},${hip - 48 * s} Q${x + f * 32 * s},${hip - 24 * s} ${x + f * 17 * s},${hip} M${x + f * 17 * s},${hip - 48 * s} L${x + f * 17 * s},${hip}`;
  return (
    <g>
      <path d={d} stroke={COL.ink} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <rect x={x - 6 * s} y={hip - 31 * s} width={12 * s} height={21 * s} fill={patch} />
      <circle cx={x} cy={hip - 43 * s} r={9 * s} fill={COL.ink} />
      {plume && <path d={`M${x},${hip - 52 * s} q${-f * 6 * s},${-9 * s} ${-f * 14 * s},${-6 * s}`} stroke={plume} strokeWidth={Math.max(1.3, 3 * s)} strokeLinecap="round" fill="none" />}
    </g>
  );
};

export type Mix = { bow?: number; spear?: number; sword?: number };

const pick = (r: number, mix: Mix): Gear => {
  const bow = mix.bow ?? 0;
  const spear = mix.spear ?? 0;
  const sword = mix.sword ?? 0;
  const tot = bow + spear + sword || 1;
  const v = r * tot;
  return v < bow ? "bow" : v < bow + spear ? "spear" : v < bow + spear + sword ? "sword" : "none";
};

// a block of soldiers: `rows` ranks receding upward (each smaller by `falloff`), `cols` per rank
export const Formation: React.FC<{
  x: number; // centre x
  y: number; // feet of the FRONT rank
  cols: number;
  rows: number;
  dx: number; // column spacing at the front rank
  dy: number; // vertical step between ranks
  s?: number; // front rank scale
  falloff?: number;
  facing: 1 | -1;
  mix: Mix;
  patch: string;
  plume?: string;
  seed?: string;
  jitter?: number;
}> = ({ x, y, cols, rows, dx, dy, s = 1, falloff = 0.94, facing, mix, patch, plume, seed = "fm", jitter = 0.18 }) => {
  const out: React.ReactNode[] = [];
  for (let r = rows - 1; r >= 0; r--) {
    const sr = s * Math.pow(falloff, r);
    const yr = y - r * dy;
    for (let c = 0; c < cols; c++) {
      const k = `${seed}-${r}-${c}`;
      const jx = (random(`${k}x`) - 0.5) * dx * sr / s * jitter * 2;
      const jy = (random(`${k}y`) - 0.5) * dy * 0.5;
      const sv = sr * (0.92 + random(`${k}s`) * 0.16);
      out.push(
        <Soldier
          key={k}
          x={x + (c - (cols - 1) / 2) * dx * (sr / s) + jx}
          y={yr + jy}
          s={sv}
          facing={facing}
          gear={pick(random(`${k}g`), mix)}
          patch={patch}
          plume={plume && random(`${k}p`) < 0.12 ? plume : undefined}
        />,
      );
    }
  }
  return <g>{out}</g>;
};

// sharpened stakes planted in the ground, leaning toward the enemy (`lean` = +1 right, -1 left)
export const Stakes: React.FC<{ x: number; y: number; n: number; dx: number; dy?: number; s?: number; lean?: 1 | -1; seed?: string }> = ({ x, y, n, dx, dy = 0, s = 1, lean = 1, seed = "st" }) => (
  <g stroke={COL.ink} strokeWidth={Math.max(1.5, 3 * s)} strokeLinecap="round">
    {Array.from({ length: n }).map((_, i) => {
      const px = x + i * dx + (random(`${seed}${i}`) - 0.5) * dx * 0.3;
      const py = y + i * dy;
      return <line key={i} x1={px} y1={py} x2={px + lean * 14 * s} y2={py - 24 * s} />;
    })}
  </g>
);
