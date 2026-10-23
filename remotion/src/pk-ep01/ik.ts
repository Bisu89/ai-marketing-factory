import { solve } from "../stickman/stick";
import type { Pose } from "../stickman/stick";

// Small maths + two-bone arm IK shared by the code-only Packed Light scenes.

export type V2 = [number, number];
export const rad = (d: number) => (d * Math.PI) / 180;
export const deg = (r: number) => (r * 180) / Math.PI;
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const sstep = (x: number) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};
// 0 -> 1 over r frames after a, 1 -> 0 over r frames before b
export const win = (t: number, a: number, b: number, r = 10) => sstep((t - a) / r) * sstep((b - t) / r);
export const wrap = (d: number) => ((((d + 180) % 360) + 360) % 360) - 180;

export const shoulderOf = (p: Pose, s: number, facing: number): V2 => {
  const j = solve(p, s, facing);
  return [j.hip[0] + 0.92 * (j.neck[0] - j.hip[0]), j.hip[1] + 0.92 * (j.neck[1] - j.hip[1])];
};

// arm angles (stick.tsx convention) that put the hand on `tgt`
export const ik = (p: Pose, s: number, facing: number, tgt: V2) => {
  const [sx, sy] = shoulderOf(p, s, facing);
  const dx = (tgt[0] - sx) * facing;
  const dy = tgt[1] - sy;
  const L1 = 40 * s;
  const L2 = 38 * s;
  const d = Math.max(Math.abs(L1 - L2) + 0.5, Math.min(Math.hypot(dx, dy), L1 + L2 - 0.5));
  const phi = deg(Math.atan2(dx, dy));
  const g = deg(Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))));
  const a1w = phi - g;
  const ex = Math.sin(rad(a1w)) * L1;
  const ey = Math.cos(rad(a1w)) * L1;
  const a2w = deg(Math.atan2(dx - ex, dy - ey));
  return { a1: a1w - -p.lean, a2: a2w - a1w };
};

export type Reach = { a: number; b: number; arm: "l" | "r"; r?: number; tgt: (t: number, q: Pose) => V2 };

export const applyReaches = (reaches: Reach[], s: number, facing: 1 | -1, t: number, p: Pose): Pose => {
  let q = p;
  for (const r of reaches) {
    const w = win(t, r.a, r.b, r.r ?? 10);
    if (w <= 0) continue;
    const { a1, a2 } = ik(q, s, facing, r.tgt(t, q));
    const k1 = r.arm === "l" ? "la1" : "ra1";
    const k2 = r.arm === "l" ? "la2" : "ra2";
    q = { ...q, [k1]: q[k1] + wrap(a1 - q[k1]) * w, [k2]: q[k2] + wrap(a2 - q[k2]) * w };
  }
  return q;
};
