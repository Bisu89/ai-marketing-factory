import { SMOOTH } from "../stickman/stick";
import type { Key, Pose } from "../stickman/stick";

// A tiny "script a character in time" kit for the code-only Packed Light scenes.
// Steps run one after another; every step starts from wherever the previous one ended, so poses blend smoothly.
//   const tl = build({ x: 300 }, ground, 1, scale, [walk(1350), wait(10), to(30, BEND), mark("down"), ...]);
// The result gives Actor-style keys + a procedural mod (walk cycle) + facing, and named frame markers.

export type Ctx = { gy: number; x: number; s: number };
type Target = Partial<Pose> | ((c: Ctx) => Partial<Pose>);
export type Step = (c: Ctx, at: number) => { keys: Key[]; end: number; mod?: (f: number, p: Pose) => Pose; face?: [number, 1 | -1]; mark?: [string, number] };

export const REST: Partial<Pose> = { lean: 0, head: 0, rot: 0, la1: -18, la2: 8, ra1: 18, ra2: -8, ll1: -12, ll2: 4, rl1: 12, rl2: -4 };

const lin = (t: number) => t;
const during = (a: number, b: number, fn: (t: number, p: Pose) => Pose) => (t: number, p: Pose) => (t >= a && t < b ? fn(t, p) : p);

const add = (p: Pose, d: Partial<Pose>, k: number): Pose => {
  const o = { ...p };
  (Object.keys(d) as (keyof Pose)[]).forEach((n) => {
    o[n] = o[n] + (d[n] as number) * k;
  });
  return o;
};

export const wait =
  (d: number): Step =>
  (_c, at) => ({ keys: [{ f: at + d, p: {} }], end: at + d });

export const to =
  (d: number, target: Target, e: (t: number) => number = SMOOTH): Step =>
  (c, at) => ({ keys: [{ f: at, p: {} }, { f: at + d, p: typeof target === "function" ? target(c) : target, e }], end: at + d });

export const face =
  (dir: 1 | -1): Step =>
  (_c, at) => ({ keys: [], end: at, face: [at, dir] });

export const mark =
  (name: string): Step =>
  (_c, at) => ({ keys: [], end: at, mark: [name, at] });

// walk (legs always, arms swing only when `arms`) to x at `speed` px/frame; the leg stride is tuned to the speed
export const walk =
  (x: number, speed: number, arms = false): Step =>
  (c, at) => {
    const x0 = c.x;
    const dur = Math.max(2, Math.round(Math.abs(x - x0) / speed));
    const end = at + dur;
    c.x = x;
    return {
      keys: [{ f: at, p: {} }, { f: end, p: { x }, e: lin }],
      end,
      face: [at, x >= x0 ? 1 : -1],
      mod: during(at, end, (t, p) => {
        const k = Math.min(1, (t - at) / 8, (end - t) / 8);
        const ph = t * 0.28;
        const sn = Math.sin(ph);
        const legs: Partial<Pose> = { ll1: -22 * sn, ll2: 10 + 14 * Math.max(0, sn), rl1: 22 * sn, rl2: 10 + 14 * Math.max(0, -sn) };
        const arm: Partial<Pose> = arms ? { la1: 20 * sn, ra1: -20 * sn } : {};
        return add(p, { ...legs, ...arm }, Math.max(0, k));
      }),
    };
  };

// repeat a small wobble on some joints between a and b (rope tying, nodding...)
export const wobble =
  (d: number, amp: Partial<Pose>, speed = 0.5): Step =>
  (_c, at) => ({
    keys: [{ f: at + d, p: {} }],
    end: at + d,
    mod: during(at, at + d, (t, p) => add(p, amp, Math.sin((t - at) * speed) * Math.min(1, (t - at) / 6, (at + d - t) / 6))),
  });

export const build = (start: Partial<Pose> & { x: number }, gy: number, facing: 1 | -1, s: number, steps: Step[]) => {
  const c: Ctx = { gy, x: start.x, s };
  const keys: Key[] = [{ f: 0, p: { ...REST, ...start, y: gy } }];
  const mods: ((f: number, p: Pose) => Pose)[] = [];
  const faces: [number, 1 | -1][] = [[0, facing]];
  const marks: Record<string, number> = {};
  let t = 0;
  for (const st of steps) {
    const m = st(c, t);
    keys.push(...m.keys);
    if (m.mod) mods.push(m.mod);
    if (m.face) faces.push(m.face);
    if (m.mark) marks[m.mark[0]] = m.mark[1];
    t = m.end;
  }
  keys.sort((a, b) => a.f - b.f);
  return {
    keys,
    marks,
    end: t,
    mod: (f: number, p: Pose) => mods.reduce((q, m) => m(f, q), p),
    facing: (f: number): 1 | -1 => faces.reduce<1 | -1>((d, [ff, v]) => (f >= ff ? v : d), facing),
  };
};
export type Timeline = ReturnType<typeof build>;
