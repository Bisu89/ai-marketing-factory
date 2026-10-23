import React from "react";
import { COL } from "./fx";
import type { Joints } from "./stick";

// Clothing for the stick body: a torso garment anchored to the neck/hip joints, rotating with
// the torso's lean like the `tie` accessory does. The limbs stay the plain stick lines (drawn on
// top), so pair this with Actor/Figure's `behind` render prop — drawn first, under everything:
//   <Actor f={f} keys={...} color={COL.ink} behind={(j) => <Outfit j={j} type="samurai" />}>
export type OutfitType = "samurai" | "soldier" | "none";

export const Outfit: React.FC<{
  j: Joints;
  scale?: number;
  type: OutfitType;
  color?: string; // main garment color
  trim?: string; // sash/belt accent color
}> = ({ j, scale = 1, type, color, trim }) => {
  if (type === "none") return null;
  const [nx, ny] = j.neck;
  const [hx, hy] = j.hip;
  const dx = hx - nx,
    dy = hy - ny;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len,
    uy = dy / len; // unit vector along the torso, neck -> hip
  const px = -uy,
    py = ux; // perpendicular unit vector
  const at = (along: number, side: number): [number, number] => [nx + ux * along + px * side, ny + uy * along + py * side];
  const seg = (pts: [number, number][]) => pts.map((p) => p.join(",")).join(" ");

  if (type === "samurai") {
    const main = color ?? "#2b4a6f";
    const accent = trim ?? COL.red;
    const shoulderW = 30 * scale,
      hipW = 24 * scale,
      hem = len * 1.3; // the kimono falls a bit past the hip (len is the neck->hip distance)
    return (
      <g>
        <polygon
          points={seg([at(-4 * scale, -shoulderW), at(-4 * scale, shoulderW), at(hem, hipW), at(hem, -hipW)])}
          fill={main}
          stroke={COL.ink}
          strokeWidth={4 * scale}
          strokeLinejoin="round"
        />
        <line
          x1={at(len * 0.95, -hipW * 0.9)[0]}
          y1={at(len * 0.95, -hipW * 0.9)[1]}
          x2={at(len * 0.95, hipW * 0.9)[0]}
          y2={at(len * 0.95, hipW * 0.9)[1]}
          stroke={accent}
          strokeWidth={9 * scale}
          strokeLinecap="round"
        />
        <polygon points={seg([at(-6 * scale, -shoulderW * 0.5), at(2 * scale, -shoulderW * 1.6), at(8 * scale, -shoulderW * 0.9)])} fill={main} stroke={COL.ink} strokeWidth={3 * scale} strokeLinejoin="round" />
        <polygon points={seg([at(-6 * scale, shoulderW * 0.5), at(2 * scale, shoulderW * 1.6), at(8 * scale, shoulderW * 0.9)])} fill={main} stroke={COL.ink} strokeWidth={3 * scale} strokeLinejoin="round" />
      </g>
    );
  }

  // soldier: a snug jacket with a belt
  const main = color ?? "#4a5a3a";
  const accent = trim ?? "#2a2a2a";
  const w = 26 * scale;
  return (
    <g>
      <polygon
        points={seg([at(-4 * scale, -w), at(-4 * scale, w), at(len * 1.02, w * 0.9), at(len * 1.02, -w * 0.9)])}
        fill={main}
        stroke={COL.ink}
        strokeWidth={4 * scale}
        strokeLinejoin="round"
      />
      <line x1={at(len * 0.82, -w * 0.95)[0]} y1={at(len * 0.82, -w * 0.95)[1]} x2={at(len * 0.82, w * 0.95)[0]} y2={at(len * 0.82, w * 0.95)[1]} stroke={accent} strokeWidth={8 * scale} />
    </g>
  );
};
