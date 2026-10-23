import { SMOOTH, SNAP, addPose, runCycle, walkCycle } from "./stick";
import type { Key, Pose } from "./stick";

// Named actions you chain instead of hand-writing keyframes. Each move is a function of the
// running context (ground y, current x, scale) and returns Actor keys plus an optional `mod`
// (procedural leg/arm cycle). Chain them in time order, one after another without overlapping:
//   <Hero f={f} who="samurai" x={400} moves={[walkTo(0, 50, 900), bow(56), wave(110)]} />
// Hero (cast.tsx) composes them for you; `compose` is exported for using them on a bare Actor.

export type Ctx = { gy: number; x: number; s: number };
export type Move = { keys: Key[]; mod?: (f: number, p: Pose) => Pose; face?: [number, 1 | -1] };
export type MoveFn = (c: Ctx) => Move;

const REST = { lean: 0, head: 0, rot: 0, la1: -18, la2: 8, ra1: 18, ra2: -8, ll1: -12, ll2: 4, rl1: 12, rl2: -4 };
const lin = (t: number) => t;
const during = (a: number, b: number, fn: (t: number, p: Pose) => Pose) => (t: number, p: Pose) => (t >= a && t < b ? fn(t, p) : p);
const scaled = (d: Partial<Pose>, k: number): Partial<Pose> => {
  const o: Partial<Pose> = {};
  (Object.keys(d) as (keyof Pose)[]).forEach((n) => {
    o[n] = (d[n] as number) * k;
  });
  return o;
};

// walk (or run) from the current x to `x` between frames `from` and `to`; turns to face the way it goes
export const walkTo =
  (from: number, to: number, x: number, run = false): MoveFn =>
  (c) => {
    const x0 = c.x;
    c.x = x;
    return {
      face: [from, x >= x0 ? 1 : -1],
      keys: [
        { f: from, p: { ...REST, x: x0, y: c.gy } },
        { f: to, p: { x }, e: lin },
      ],
      mod: during(from, to, (t, p) => {
        const k = Math.min(1, (t - from) / 6, (to - t) / 6);
        return addPose(p, scaled(run ? runCycle(t, 0.5) : walkCycle(t, 0.3), Math.max(0, k)));
      }),
    };
  };

export const bow =
  (at: number, dur = 40): MoveFn =>
  (c) => ({
    keys: [
      { f: at, p: { ...REST, y: c.gy } },
      { f: at + dur * 0.35, p: { lean: 40, head: 12, la1: -6, ra1: 6 }, e: SMOOTH },
      { f: at + dur * 0.7, p: {} },
      { f: at + dur, p: { ...REST }, e: SMOOTH },
    ],
  });

export const jump =
  (at: number, h = 150): MoveFn =>
  (c) => ({
    keys: [
      { f: at, p: { ...REST, y: c.gy } },
      { f: at + 6, p: { y: c.gy + 16 * c.s, ll1: -40, ll2: 70, rl1: 40, rl2: 70, lean: 6, la1: -40, ra1: 40 } },
      { f: at + 16, p: { y: c.gy - h * c.s, ll1: -15, ll2: 30, rl1: 15, rl2: 30, la1: -70, ra1: 70, lean: 0 }, e: SMOOTH },
      { f: at + 26, p: { y: c.gy, ll1: -30, ll2: 60, rl1: 30, rl2: 60 }, e: SMOOTH },
      { f: at + 34, p: { ...REST, y: c.gy }, e: SMOOTH },
    ],
  });

// fall backwards and lie on the ground (the big head keeps the body slightly raised)
export const fall =
  (at: number): MoveFn =>
  (c) => {
    const lie = c.gy + 52 * c.s;
    return {
      keys: [
        { f: at, p: { ...REST, y: c.gy } },
        { f: at + 8, p: { rot: -20, lean: -12, la1: -120, ra1: 120, y: c.gy - 10 * c.s }, e: SNAP },
        { f: at + 22, p: { rot: -90, lean: 0, y: lie, la1: -60, la2: 0, ra1: 60, ra2: 0, ll1: -20, rl1: 20 }, e: SMOOTH },
        { f: at + 28, p: { y: lie - 14 * c.s } },
        { f: at + 34, p: { y: lie }, e: SMOOTH },
      ],
    };
  };

export const punch =
  (at: number): MoveFn =>
  (c) => ({
    keys: [
      { f: at, p: { ...REST, y: c.gy } },
      { f: at + 6, p: { lean: -10, ra1: -30, ra2: -60, la1: -40, la2: -110 } },
      { f: at + 10, p: { lean: 14, ra1: 92, ra2: 0, ll1: -30, ll2: 10, rl1: 35, rl2: -5 }, e: SNAP },
      { f: at + 20, p: {} },
      { f: at + 30, p: { ...REST }, e: SMOOTH },
    ],
  });

// raise the arm to the side and wave it for `dur` frames
export const wave =
  (at: number, dur = 60): MoveFn =>
  (c) => ({
    keys: [
      { f: at, p: { ...REST, y: c.gy } },
      { f: at + 8, p: { ra1: 110, ra2: -20 }, e: SNAP },
      { f: at + dur, p: {} },
      { f: at + dur + 8, p: { ...REST }, e: SMOOTH },
    ],
    mod: during(at + 8, at + dur, (t, p) => ({ ...p, ra2: p.ra2 + Math.sin(t * 0.55) * 35 })),
  });

// strike any pose from stick.tsx's P (e.g. pose(40, P.shrug)) and hold it, then relax
export const pose =
  (at: number, p: Partial<Pose>, hold = 30): MoveFn =>
  (c) => ({
    keys: [
      { f: at, p: { ...REST, y: c.gy } },
      { f: at + 8, p, e: SNAP },
      { f: at + 8 + hold, p: {} },
      { f: at + 16 + hold, p: { ...REST }, e: SMOOTH },
    ],
  });

// instantly turn to face left (-1) or right (1)
export const turn =
  (at: number, dir: 1 | -1): MoveFn =>
  () => ({ keys: [], face: [at, dir] });

export const compose = (c: Ctx, fns: MoveFn[], facing: 1 | -1) => {
  const ms = fns.map((fn) => fn(c));
  const keys = ms.reduce<Key[]>((a, m) => a.concat(m.keys), []).sort((a, b) => a.f - b.f);
  const mods = ms.reduce<((f: number, p: Pose) => Pose)[]>((a, m) => (m.mod ? a.concat([m.mod]) : a), []);
  const faces = ms.reduce<[number, 1 | -1][]>((a, m) => (m.face ? a.concat([m.face]) : a), []).sort((a, b) => a[0] - b[0]);
  return {
    keys,
    mod: (t: number, p: Pose) => mods.reduce((q, m) => m(t, q), p),
    facing: (t: number): 1 | -1 => faces.reduce<1 | -1>((d, [f, v]) => (t >= f ? v : d), facing),
  };
};
