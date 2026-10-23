import React from "react";
import { useCurrentFrame } from "remotion";
import { Actor, SMOOTH, STAND, poseAt, solve } from "../stickman/stick";
import type { Key, Pose } from "../stickman/stick";
import { COL } from "../stickman/fx";
import { Stage } from "../stickman/common";

// PACKED LIGHT ep1, scene 7 (the knife / feather-stick lesson). Test scene: no voice, no sfx.
// Two stick figures sit on a log. Arms are placed with two-bone IK so hands really meet at the
// knife and the stick (moves.ts has no hand-targeted moves yet).

export const DURATION = 1700;

type V2 = [number, number];
const rad = (d: number) => (d * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const sstep = (x: number) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};
const win = (t: number, a: number, b: number, r = 12) => sstep((t - a) / r) * sstep((b - t) / r);
const wrap = (d: number) => ((((d + 180) % 360) + 360) % 360) - 180;
const unit = (x: number, y: number): V2 => {
  const l = Math.hypot(x, y) || 1;
  return [x / l, y / l];
};

// ---------- cast ----------
const SITL: Partial<Pose> = { y: 800, ll1: 80, ll2: -80, rl1: 92, rl2: -82 };
const DAD = { s: 1, color: COL.ink };
const SON = { s: 0.82, color: COL.blue };
const baseDad: Partial<Pose> = { x: 850, lean: -3, ...SITL, la1: 25, la2: 65, ra1: 20, ra2: 60 };
const baseSon: Partial<Pose> = { x: 935, lean: 8, ...SITL, la1: 25, la2: 65, ra1: 20, ra2: 60 };

const K = (f: number, p: Partial<Pose> = {}): Key => ({ f, p, e: SMOOTH });

const dadKeys: Key[] = [
  K(0),
  K(240),
  K(268, { x: 806, lean: -12, head: -6 }),
  K(350),
  K(385, { x: 850, lean: -3, head: 0 }),
  K(640),
  K(660, { lean: 4, head: 8 }),
  K(750),
  K(775, { lean: -3, head: 0, x: 850 }),
  K(800, { x: 815, lean: 6, head: 4 }),
  K(990),
  K(1010, { lean: -2, head: 0 }),
  K(1030, { x: 850 }),
  K(1440),
  K(1485, { x: 882, lean: 2 }),
  K(1700),
];

const sonKeys: Key[] = [
  K(0),
  K(80, { lean: 11, head: 5 }),
  K(200),
  K(222, { lean: 16, head: -4 }),
  K(245),
  K(262, { ra1: 92, ra2: 0 }),
  K(345, { ra1: 452 }),
  K(362, { ra1: 380, ra2: 60 }),
  K(780),
  K(800, { lean: 2, head: 6 }),
  K(990),
  K(1030, { lean: 14, head: -4 }),
  K(1700),
];

const sonFace = (t: number): 1 | -1 => (t < 205 ? -1 : t < 787 ? 1 : t < 1030 ? -1 : 1);
const dadFace = (): 1 | -1 => 1;

// ---------- pose + IK helpers ----------
const keyPose = (keys: Key[], base: Partial<Pose>, t: number): Pose => poseAt(t, keys, { ...STAND, ...base });

const shoulderOf = (p: Pose, s: number, facing: number): V2 => {
  const j = solve(p, s, facing);
  return [j.hip[0] + 0.92 * (j.neck[0] - j.hip[0]), j.hip[1] + 0.92 * (j.neck[1] - j.hip[1])];
};

const ik = (p: Pose, s: number, facing: number, tgt: V2) => {
  const [sx, sy] = shoulderOf(p, s, facing);
  const dx = (tgt[0] - sx) * facing;
  const dy = tgt[1] - sy;
  const L1 = 40 * s;
  const L2 = 38 * s;
  const d = Math.max(Math.abs(L1 - L2) + 0.5, Math.min(Math.hypot(dx, dy), L1 + L2 - 0.5));
  const phi = deg(Math.atan2(dx, dy));
  const g = deg(Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))));
  const a1w = phi - g; // elbow below the shoulder-target line
  const ex = Math.sin(rad(a1w)) * L1;
  const ey = Math.cos(rad(a1w)) * L1;
  const a2w = deg(Math.atan2(dx - ex, dy - ey));
  const body = -p.lean;
  return { a1: a1w - body, a2: a2w - a1w };
};

type Reach = { a: number; b: number; arm: "l" | "r"; r?: number; tgt: (t: number, q: Pose) => V2 };

const makeMod =
  (s: number, face: (t: number) => 1 | -1, reaches: Reach[], extra?: (t: number, p: Pose) => Pose) =>
  (t: number, p: Pose): Pose => {
    let q: Pose = { ...p, y: p.y + Math.sin(t * 0.1) * 1.2 };
    for (const r of reaches) {
      const w = win(t, r.a, r.b, r.r ?? 12);
      if (w <= 0) continue;
      const { a1, a2 } = ik(q, s, face(t), r.tgt(t, q));
      const k1 = r.arm === "l" ? "la1" : "ra1";
      const k2 = r.arm === "l" ? "la2" : "ra2";
      q = { ...q, [k1]: q[k1] + wrap(a1 - q[k1]) * w, [k2]: q[k2] + wrap(a2 - q[k2]) * w };
    }
    return extra ? extra(t, q) : q;
  };

// ---------- strokes, stick, curls ----------
type Stroke = { a: number; b: number; s0: number; s1: number };
const contactS = (t: number, ss: Stroke[]) => {
  let s = ss[0].s0;
  for (let i = 0; i < ss.length; i++) {
    const k = ss[i];
    const prevEnd = i > 0 ? ss[i - 1].s1 : k.s0;
    const retStart = i > 0 ? ss[i - 1].b : k.a - 10;
    if (t < k.a) return lerp(prevEnd, k.s0, sstep((t - retStart) / (k.a - retStart)));
    if (t <= k.b) return lerp(k.s0, k.s1, (t - k.a) / (k.b - k.a));
    s = k.s1;
  }
  return s;
};

const strokes1: Stroke[] = [
  { a: 470, b: 502, s0: 0.3, s1: 0.5 },
  { a: 514, b: 546, s0: 0.3, s1: 0.5 },
  { a: 558, b: 590, s0: 0.3, s1: 0.5 },
];
const strokesDad: Stroke[] = [
  { a: 836, b: 896, s0: 0.2, s1: 0.62 },
  { a: 902, b: 962, s0: 0.3, s1: 0.72 },
];
const strokes2: Stroke[] = Array.from({ length: 8 }, (_, i) => {
  const lo = 0.16 + (i % 4) * 0.18;
  return { a: 1052 + i * 38, b: 1052 + i * 38 + 32, s0: lo, s1: lo + 0.15 };
});

const STICK_LEN = 88;
const ANG_SON = 48;
const ANG_DAD = 80;
const K_L: V2 = [885, 772]; // dad's left hand when he holds the stick for the demo
const X1: V2 = [888, 774]; // knife hand-over point 1
const X2: V2 = [872, 786]; // hand-over point 2

const sonGrip = (t: number, q: Pose): { g: V2; u: V2 } => {
  const f = sonFace(t);
  const sh = shoulderOf(q, SON.s, f);
  const holding = t < 205 || (t >= 787 && t < 1030);
  const ang = rad(holding ? 100 : ANG_SON);
  return { g: [sh[0] + f * 46, sh[1] + 36], u: [f * Math.cos(ang), -Math.sin(ang)] };
};
const dadGrip = (): { g: V2; u: V2 } => ({ g: K_L, u: [Math.cos(rad(ANG_DAD)), -Math.sin(rad(ANG_DAD))] });

const stickGeom = (t: number): { a: V2; u: V2 } => {
  const sg = sonGrip(t, keyPose(sonKeys, baseSon, t));
  const dg = dadGrip();
  const toA = (h: { g: V2; u: V2 }) => ({ a: [h.g[0] - h.u[0] * 14, h.g[1] - h.u[1] * 14] as V2, u: h.u });
  const S = toA(sg);
  const D = toA(dg);
  let w = 0;
  if (t >= 790 && t < 830) w = sstep((t - 790) / 40);
  else if (t >= 830 && t < 960) w = 1;
  else if (t >= 960 && t < 1000) w = 1 - sstep((t - 960) / 40);
  if (w === 0) return S;
  return { a: [lerp(S.a[0], D.a[0], w), lerp(S.a[1], D.a[1], w)], u: unit(lerp(S.u[0], D.u[0], w), lerp(S.u[1], D.u[1], w)) };
};
const onStick = (g: { a: V2; u: V2 }, s: number, off = 0): V2 => [
  g.a[0] + g.u[0] * STICK_LEN * s + g.u[1] * off,
  g.a[1] + g.u[1] * STICK_LEN * s - g.u[0] * off,
];

const V0_SON = (): V2 => unit(sonFace(900) * 0.85, 0.53);
const V0_DAD: V2 = unit(0.95, 0.31);
const HANDLE = 38;

// ---------- reaches ----------
const sonReaches: Reach[] = [
  { a: 0, b: 806, arm: "l", r: 10, tgt: (t, q) => sonGrip(t, q).g },
  { a: 985, b: 1700, arm: "l", r: 12, tgt: (t, q) => sonGrip(t, q).g },
  { a: 138, b: 205, arm: "r", tgt: () => X1 },
  {
    a: 440,
    b: 600,
    arm: "r",
    tgt: (t, q) => {
      const g = stickGeom(t);
      void q;
      const c = onStick(g, contactS(t, strokes1));
      const v = V0_SON();
      return [c[0] - v[0] * HANDLE, c[1] - v[1] * HANDLE];
    },
  },
  { a: 792, b: 842, arm: "r", tgt: () => X2 },
  { a: 962, b: 1022, arm: "r", tgt: () => X2 },
  {
    a: 1040,
    b: 1445,
    arm: "r",
    tgt: (t) => {
      const c = onStick(stickGeom(t), contactS(t, strokes2));
      const v = V0_SON();
      return [c[0] - v[0] * HANDLE, c[1] - v[1] * HANDLE];
    },
  },
];

const dadReaches: Reach[] = [
  { a: 118, b: 205, arm: "r", tgt: () => X1 },
  { a: 802, b: 968, arm: "l", tgt: () => K_L },
  {
    a: 802,
    b: 966,
    arm: "r",
    tgt: (t) => {
      const c = onStick(stickGeom(t), contactS(t, strokesDad));
      const demo: V2 = [c[0] - V0_DAD[0] * HANDLE, c[1] - V0_DAD[1] * HANDLE];
      const m = sstep((t - 830) / 12);
      return [lerp(X2[0], demo[0], m), lerp(X2[1], demo[1], m)];
    },
  },
  { a: 958, b: 1012, arm: "r", tgt: () => X2 },
  {
    a: 1470,
    b: 1700,
    arm: "r",
    tgt: (t) => {
      const sq = keyPose(sonKeys, baseSon, t);
      const sh = shoulderOf(sq, SON.s, sonFace(t));
      return [sh[0] - 8, sh[1] + 6];
    },
  },
];

const sonExtra = (t: number, p: Pose): Pose => {
  if (t > 1500) return { ...p, ra2: p.ra2 + Math.sin(t * 0.55) * 14 * sstep((t - 1500) / 20) };
  return p;
};

const dadMod = makeMod(DAD.s, dadFace, dadReaches);
const sonMod = makeMod(SON.s, sonFace, sonReaches, sonExtra);

const poseNow = (who: "dad" | "son", t: number): Pose => {
  const keys = who === "dad" ? dadKeys : sonKeys;
  const base = who === "dad" ? baseDad : baseSon;
  const mod = who === "dad" ? dadMod : sonMod;
  return mod(t, keyPose(keys, base, t));
};

// ---------- props ----------
const Knife: React.FC<{ hand: V2; dir: V2; open: number }> = ({ hand, dir, open }) => {
  const [dx, dy] = dir;
  const nx = -dy;
  const ny = dx;
  const p = (a: number, n = 0): string => `${hand[0] + dx * a + nx * n},${hand[1] + dy * a + ny * n}`;
  return (
    <g>
      <line x1={hand[0] - dx * 8} y1={hand[1] - dy * 8} x2={hand[0] + dx * 26} y2={hand[1] + dy * 26} stroke="#5b3a1e" strokeWidth={11} strokeLinecap="round" />
      {open > 0.02 && (
        <polygon points={`${p(24, -4)} ${p(24 + 40 * open, -1)} ${p(24, 4)}`} fill="#c9ced3" stroke="#6b7078" strokeWidth={2} strokeLinejoin="round" />
      )}
    </g>
  );
};

const Stick: React.FC<{ a: V2; u: V2 }> = ({ a, u }) => {
  const b: V2 = [a[0] + u[0] * STICK_LEN, a[1] + u[1] * STICK_LEN];
  return (
    <g strokeLinecap="round">
      <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#8c7a4f" strokeWidth={15} />
      <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#eadfb8" strokeWidth={10} />
    </g>
  );
};

type Curl = Stroke & { side: 1 | -1 };
const curls: Curl[] = [
  ...strokesDad.map((s) => ({ ...s, side: 1 as const })),
  ...strokes2.map((s, i) => ({ ...s, side: (i < 4 ? -1 : 1) as 1 | -1 })),
];

const CurlShape: React.FC<{ c: Curl; t: number; g: { a: V2; u: V2 } }> = ({ c, t, g }) => {
  const q = clamp01((t - c.a) / (c.b - c.a));
  if (q <= 0) return null;
  const n: V2 = [g.u[1] * c.side, -g.u[0] * c.side];
  const p0 = onStick(g, c.s0);
  const p1 = onStick(g, c.s0 + (c.s1 - c.s0) * q);
  const bulge = 6 + 12 * sstep(q);
  const mid: V2 = [(p0[0] + p1[0]) / 2 + n[0] * bulge * 1.3, (p0[1] + p1[1]) / 2 + n[1] * bulge * 1.3];
  const end: V2 = [p1[0] + n[0] * bulge * 0.7, p1[1] + n[1] * bulge * 0.7];
  return <path d={`M${p0[0]},${p0[1]} Q${mid[0]},${mid[1]} ${end[0]},${end[1]}`} fill="none" stroke="#d6bf86" strokeWidth={5} strokeLinecap="round" />;
};

const Chips: React.FC<{ t: number }> = ({ t }) => (
  <g>
    {strokes1.flatMap((k, i) =>
      [0, 1, 2].map((j) => {
        const age = t - (k.b - 6);
        if (age < 0 || age > 34) return null;
        const g = stickGeom(k.b);
        const c = onStick(g, k.s1);
        const vx = (j - 1) * 2.4 + 1.2;
        const x = c[0] + vx * age;
        const y = c[1] + -4 * age + 0.5 * 0.55 * age * age;
        return (
          <rect key={`${i}-${j}`} x={x} y={y} width={9} height={5} rx={1.5} fill="#e2d4a6" stroke="#8c7a4f" strokeWidth={1.5} opacity={1 - age / 34} transform={`rotate(${age * (6 + j * 4)} ${x} ${y})`} />
        );
      }),
    )}
  </g>
);

const Ring: React.FC<{ t: number }> = ({ t }) => {
  const q = clamp01((t - 262) / 83);
  const fade = 1 - sstep((t - 350) / 20);
  if (q <= 0 || fade <= 0) return null;
  const sq = keyPose(sonKeys, baseSon, t);
  const sh = shoulderOf(sq, SON.s, 1);
  const R = (40 + 38) * SON.s;
  return (
    <g transform={`translate(${sh[0]} ${sh[1]}) scale(1 -1)`} opacity={0.75 * fade}>
      <circle r={R} fill="none" stroke={COL.blue} strokeWidth={4} pathLength={1} strokeDasharray={`${q} 2`} strokeLinecap="round" />
    </g>
  );
};

const knifeState = (t: number) => {
  const owner: "dad" | "son" = t < 172 ? "dad" : t < 815 ? "son" : t < 985 ? "dad" : "son";
  const p = poseNow(owner, t);
  const f = owner === "dad" ? 1 : sonFace(t);
  const s = owner === "dad" ? DAD.s : SON.s;
  const j = solve(p, s, f);
  const hand = j.rHand;
  let dir = unit(j.rHand[0] - j.rElbow[0], j.rHand[1] - j.rElbow[1]);
  let open = 0;
  if (owner === "son" && t >= 425 && t < 780) open = sstep((t - 425) / 10);
  if (owner === "dad" && t >= 828 && t < 955) open = sstep((t - 828) / 10);
  if (open > 0 && ((owner === "son" && t >= 440 && t < 600) || (owner === "son" && t >= 1040 && t < 1445) || (owner === "dad" && t < 966))) {
    const v = owner === "dad" ? V0_DAD : ([f * 0.85, 0.53] as V2);
    dir = unit(v[0], v[1]);
  }
  if (owner === "son" && t >= 1010 && t < 1040) open = sstep((t - 1010) / 10);
  if (owner === "son" && t >= 1040) open = 1;
  return { hand, dir, open };
};

const LINES = [
  { a: 20, b: 98, who: "SON", text: "Can I use the big knife?" },
  { a: 105, b: 195, who: "DAD", text: "This one. Smaller is easier to control." },
  { a: 205, b: 375, who: "DAD", text: "Sit. Elbows on your knees. Arm out, turn around. Anyone in reach? Anything?" },
  { a: 385, b: 412, who: "SON", text: "No." },
  { a: 420, b: 576, who: "DAD", text: "Cut away from you. Keep your other hand clear of the blade." },
  { a: 650, b: 780, who: "DAD", text: "Thinner. Shallow angle. Stop before the end of the stick." },
  { a: 1010, b: 1062, who: "SON", text: "Like peeling an apple." },
  { a: 1075, b: 1435, who: "DAD", text: "Sort of. The thin curls catch a match. But that only works if the inside is dry. If it's wet in there, all you've made is wet curls." },
  { a: 1450, b: 1665, who: "VO", text: "Ten minutes of this, and his hand is cramping. It's slow work. It's supposed to be." },
];

const Trunk: React.FC<{ x: number; h: number; w: number }> = ({ x, h, w }) => (
  <g stroke="#c9c5b8" strokeLinecap="round" fill="none">
    <rect x={x} y={862 - h} width={w} height={h} fill="#e6e2d6" stroke="#c9c5b8" strokeWidth={3} />
    <line x1={x + w / 2} y1={862 - h * 0.7} x2={x + w / 2 + 70} y2={862 - h * 0.85} strokeWidth={7} />
    <line x1={x + w / 2} y1={862 - h * 0.55} x2={x + w / 2 - 60} y2={862 - h * 0.7} strokeWidth={7} />
  </g>
);

export const Video: React.FC = () => {
  const t = useCurrentFrame();
  const g = stickGeom(t);
  const k = knifeState(t);
  const line = LINES.find((l) => t >= l.a && t < l.b);
  return (
    <Stage
      cam={{ x: -20, y: 235, z: 2.4 }}
      svg={
        <>
          <Trunk x={340} h={620} w={46} />
          <Trunk x={1560} h={700} w={52} />
          <g>
            <rect x={640} y={806} width={560} height={56} rx={26} fill="#a98a5e" stroke="#6e5736" strokeWidth={5} />
            <ellipse cx={646} cy={834} rx={14} ry={26} fill="#c9a975" stroke="#6e5736" strokeWidth={4} />
            <path d="M720,822 q40,-8 80,0 M900,848 q50,6 90,0 M1040,820 q30,-6 70,2" fill="none" stroke="#7d6540" strokeWidth={3} strokeLinecap="round" />
          </g>
          <Actor f={t} keys={dadKeys} base={baseDad} color={DAD.color} scale={DAD.s} facing={dadFace} accessory="cap" mod={dadMod} trails={false} />
          <Actor f={t} keys={sonKeys} base={baseSon} color={SON.color} scale={SON.s} facing={sonFace} mod={sonMod} trails={false} />
          <Ring t={t} />
          <Stick a={g.a} u={g.u} />
          {curls.map((c, i) => (
            <CurlShape key={i} c={c} t={t} g={g} />
          ))}
          <Chips t={t} />
          <Knife hand={k.hand} dir={k.dir} open={k.open} />
        </>
      }
      html={
        line ? (
          <div style={{ position: "absolute", left: 160, right: 160, bottom: 70, textAlign: "center", fontFamily: "Arial, sans-serif", fontSize: 40, fontWeight: 700, color: line.who === "SON" ? COL.blue : line.who === "VO" ? COL.grey : COL.ink }}>
            {line.who === "VO" ? <i>{line.text}</i> : `${line.who}: ${line.text}`}
          </div>
        ) : null
      }
    />
  );
};
