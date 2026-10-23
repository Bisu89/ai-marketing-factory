import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, random, staticFile, useCurrentFrame } from "remotion";
import { STAND, groundY, poseAt } from "../stickman/stick";
import type { Pose } from "../stickman/stick";
import { FallingLeaves, Fire } from "../stickman/weather";
import { DAD_LOOK, Puppet, SON_LOOK } from "./puppet";
import { applyReaches, lerp, shoulderOf, sstep } from "./ik";
import type { Reach, V2 } from "./ik";
import { REST, build, face, mark, to, wait, walk, wobble } from "./pk-moves";
import type { Ctx, Timeline } from "./pk-moves";

// PACKED LIGHT ep1 - CODE-ONLY animation test. No pictures, no image-to-video: the scenery is drawn with SVG, the two
// characters are puppets on the stickman engine's skeleton, and every action (walk, carry, set down, tie a rope, pick
// up, kneel, strike a match) is a keyed pose + two-bone IK. Sound effects come from tools/packed_light/gen_sfx.py.

const W = 1920;
const H = 1080;
const GROUND = 852;
const DAD_S = 1.25;
const SON_S = 1.0;
const gyDad = groundY(DAD_S);
const gySon = groundY(SON_S);
const SEAT_Y = 801;

const evalPose = (tl: Timeline, base: Partial<Pose>, t: number, s: number, reaches: Reach[] = []): Pose => {
  const p = tl.mod(t, poseAt(t, tl.keys, { ...STAND, ...base }));
  return applyReaches(reaches, s, tl.facing(t), t, p);
};

// ------------------------------------------------------------------ poses
const UP = (c: Ctx): Partial<Pose> => ({ ...REST, y: c.gy });
const BEND_SET = (c: Ctx): Partial<Pose> => ({ lean: 36, y: c.gy + 26 * c.s, ll1: -38, ll2: 66, rl1: 32, rl2: 72, ra1: 50, ra2: 0, la1: 30, la2: 0 });
const BEND_PICK = (c: Ctx): Partial<Pose> => ({ lean: 36, y: c.gy + 24 * c.s, ll1: -36, ll2: 62, rl1: 30, rl2: 68, ra1: 55, ra2: 0, la1: 45, la2: 0 });
const CARRY = (c: Ctx): Partial<Pose> => ({ ...REST, y: c.gy, lean: 3, la1: 58, la2: 70, ra1: 62, ra2: 66 });
const ARMS_UP: Partial<Pose> = { lean: 3, la1: 168, la2: 6, ra1: 152, ra2: 10, head: -8 };
const HIPS: Partial<Pose> = { lean: 0, head: 0, la1: -52, la2: 74, ra1: 52, ra2: -74 };
const SIT: Partial<Pose> = { ll1: 80, ll2: -80, rl1: 95, rl2: -85, lean: -4, la1: 34, la2: 112, ra1: 30, ra2: 118 };
const CHEER: Partial<Pose> = { la1: -155, la2: -15, ra1: 155, ra2: 15, lean: -6 };
const KNEEL = (c: Ctx): Partial<Pose> => ({ lean: 30, head: 8, y: c.gy + 40 * c.s, ll1: 82, ll2: -82, rl1: -25, rl2: -75, la1: 40, la2: 70, ra1: 40, ra2: 60 });
const THINK: Partial<Pose> = { ra1: 36, ra2: 140, la1: 30, la2: 80, head: 14 };

// ------------------------------------------------------------------ act 1: campsite
const RING_X = 1500;
const TREE_R = 1040;
const dadTL = build({ x: 300, ra1: 14, ra2: -2 }, gyDad, 1, DAD_S, [
  wait(8),
  mark("w1a"),
  walk(1350, 8),
  mark("w1b"),
  wait(4),
  to(26, BEND_SET),
  mark("down"),
  wait(8),
  to(24, UP),
  mark("w2a"),
  walk(1085, 8),
  mark("w2b"),
  wait(4),
  to(22, ARMS_UP),
  mark("tieStart"),
  wobble(64, { ra2: 24, la2: -14 }, 0.62),
  mark("tied"),
  wait(6),
  to(22, UP),
  wait(4),
  to(16, HIPS),
  wait(34),
]);
const M1 = dadTL.marks;
const sonTL1 = build({ x: 690, y: SEAT_Y, ...SIT }, SEAT_Y, 1, SON_S, [wait(M1.tied), to(12, CHEER), wait(34), to(14, SIT)]);
const ACT1 = dadTL.end;

const BUCKET_X = 1445;
const dadReach1: Reach[] = [
  { a: M1.down - 24, b: M1.down + 6, arm: "r", tgt: () => [BUCKET_X - 4, GROUND - 38] },
  { a: M1.tieStart - 4, b: M1.tied + 6, arm: "r", tgt: (t) => [1052, 572 + 3 * Math.sin(t * 0.62)] },
  { a: M1.tieStart - 4, b: M1.tied + 6, arm: "l", tgt: (t) => [1048, 592 + 3 * Math.sin(t * 0.62 + 1)] },
];

// ------------------------------------------------------------------ act 2: gathering wood
const BRANCH_X = [770, 1170, 1570];
const sonTL2 = build({ x: 250, ...REST }, gySon, 1, SON_S, [
  wait(6),
  mark("w1a"),
  walk(700, 6.4, true),
  mark("w1b"),
  to(22, BEND_PICK),
  mark("pick0"),
  to(18, CARRY),
  mark("w2a"),
  walk(1100, 6.4),
  mark("w2b"),
  to(22, BEND_PICK),
  mark("pick1"),
  to(18, CARRY),
  mark("w3a"),
  walk(1500, 6.4),
  mark("w3b"),
  to(22, BEND_PICK),
  mark("pick2"),
  to(18, CARRY),
  wait(10),
  mark("w4a"),
  walk(900, 6.4),
  mark("w4b"),
  wait(24),
]);
const M2 = sonTL2.marks;
const ACT2 = sonTL2.end;
const sonReach2: Reach[] = [0, 1, 2].flatMap((i) => {
  const m = M2["pick" + i];
  return (["l", "r"] as const).map((arm) => ({
    a: m - 20,
    b: m + 4,
    arm,
    tgt: (_t: number, q: Pose): V2 => [BRANCH_X[i] - (arm === "l" ? 8 : -8), GROUND - 18 + (q.y > 0 ? 0 : 0)],
  }));
});

// ------------------------------------------------------------------ act 3: the match
const CONE_X = 1090;
const MATCH_T: V2 = [945, 800];
const strikeSteps = [0, 1, 2].flatMap((i) => [mark("s" + i), wait(64)]);
const sonTL3 = build({ x: 420, ...REST, la1: 58, la2: 70, ra1: 62, ra2: 66, lean: 3 }, gySon, 1, SON_S, [
  wait(4),
  mark("w1a"),
  walk(850, 6.4),
  mark("w1b"),
  to(16, (c) => ({ ...REST, y: c.gy, lean: 14, la1: 40, la2: 20, ra1: 50, ra2: 10 })),
  mark("drop"),
  to(24, KNEEL),
  wait(8),
  ...strikeSteps,
  to(22, THINK),
  mark("think"),
  wait(70),
]);
const M3 = sonTL3.marks;
const ACT3 = sonTL3.end;
const boxPos = (q: Pose): V2 => {
  const sh = shoulderOf(q, SON_S, 1);
  return [sh[0] + 36, sh[1] + 28];
};
// where the hand holding the match is u frames into one strike: ready -> swipe on the box -> to the cone -> hold -> back
const matchPath = (u: number, B: V2): V2 => {
  const T = [0, 10, 18, 30, 36, 52, 64];
  const K: V2[] = [
    [B[0] - 18, B[1] - 30],
    [B[0] - 30, B[1] - 6],
    [B[0] + 32, B[1] - 4],
    [MATCH_T[0] - 12, MATCH_T[1] - 10],
    MATCH_T,
    MATCH_T,
    [B[0] - 18, B[1] - 30],
  ];
  for (let k = 0; k < 6; k++) {
    if (u <= T[k + 1]) {
      const q = sstep((u - T[k]) / (T[k + 1] - T[k]));
      return [lerp(K[k][0], K[k + 1][0], q), lerp(K[k][1], K[k + 1][1], q)];
    }
  }
  return K[6];
};
const sonReach3: Reach[] = [
  ...[0, 1, 2].flatMap((i) => {
    const a = M3["s" + i];
    return [
      { a, b: a + 64, arm: "l" as const, r: 6, tgt: (_t: number, q: Pose): V2 => boxPos(q) },
      {
        a,
        b: a + 64,
        arm: "r" as const,
        r: 6,
        tgt: (t: number, q: Pose): V2 => matchPath(t - a, boxPos(q)),
      },
    ];
  }),
];

// ------------------------------------------------------------------ audio events (frame in the whole video)
const OFF2 = ACT1;
const OFF3 = ACT1 + ACT2;
export const DURATION = ACT1 + ACT2 + ACT3;
type Ev = { frame: number; name: string; vol: number };
const steps = (a: number, b: number, off: number, name: string, vol: number): Ev[] => {
  const out: Ev[] = [];
  for (let t = a + 2; t < b - 6; t += 36) out.push({ frame: off + t, name, vol });
  return out;
};
const EVENTS: Ev[] = [
  ...steps(M1.w1a, M1.w1b, 0, "steps_gravel", 0.5),
  { frame: M1.down, name: "clink", vol: 0.6 },
  { frame: M1.down + 4, name: "slosh", vol: 0.7 },
  ...steps(M1.w2a, M1.w2b, 0, "steps_gravel", 0.5),
  { frame: M1.tieStart + 4, name: "rope", vol: 0.6 },
  { frame: M1.tieStart + 30, name: "tarp_flap", vol: 0.6 },
  { frame: M1.tied + 4, name: "bird1", vol: 0.4 },
  ...["w1", "w2", "w3", "w4"].flatMap((w) => steps(M2[w + "a"], M2[w + "b"], OFF2, "steps_leaves", 0.5)),
  ...[0, 1, 2].map((i) => ({ frame: OFF2 + M2["pick" + i] - 4, name: "branch_clatter", vol: 0.5 })),
  ...steps(M3.w1a, M3.w1b, OFF3, "steps_leaves", 0.5),
  { frame: OFF3 + M3.drop, name: "branch_clatter", vol: 0.6 },
  ...[0, 1, 2].flatMap((i) => [
    { frame: OFF3 + M3["s" + i] + 9, name: "match_strike", vol: 0.8 },
    { frame: OFF3 + M3["s" + i] + 40, name: "smoke_hiss", vol: 0.45 },
  ]),
  { frame: OFF3 + M3.think, name: "twig_snap", vol: 0.0 },
];

// ------------------------------------------------------------------ scenery
const pine = (x: number, base: number, h: number, col: string, key: string | number) => (
  <g key={key}>
    <rect x={x - h * 0.03} y={base - h * 0.12} width={h * 0.06} height={h * 0.12} fill="#4a2f1d" />
    <polygon points={`${x},${base - h} ${x - h * 0.22},${base - h * 0.55} ${x + h * 0.22},${base - h * 0.55}`} fill={col} />
    <polygon points={`${x},${base - h * 0.72} ${x - h * 0.3},${base - h * 0.28} ${x + h * 0.3},${base - h * 0.28}`} fill={col} />
    <polygon points={`${x},${base - h * 0.45} ${x - h * 0.38},${base - h * 0.1} ${x + h * 0.38},${base - h * 0.1}`} fill={col} />
  </g>
);

const PineRow: React.FC<{ camX: number; par: number; seed: string; n: number; base: number; h: [number, number]; col: string; span: number }> = ({ camX, par, seed, n, base, h, col, span }) => (
  <g>
    {Array.from({ length: n }).map((_, i) => {
      const wx = (i / n) * span + (random(seed + i) - 0.5) * (span / n) * 0.9;
      const x = wx - camX * par;
      if (x < -250 || x > W + 250) return null;
      return pine(x, base, h[0] + (h[1] - h[0]) * random(seed + "h" + i), col, i);
    })}
  </g>
);

const Hills: React.FC<{ camX: number; par: number; base: number; amp: number; col: string; ph: number }> = ({ camX, par, base, amp, col, ph }) => {
  const o = camX * par;
  const p: string[] = [];
  for (let x = -40; x <= W + 40; x += 40) {
    const wx = x + o;
    p.push(`${x},${base - amp * (Math.sin(wx / 310 + ph) + 0.5 * Math.sin(wx / 130 + ph * 2) + 1)}`);
  }
  return <polygon points={`-40,${H} ${p.join(" ")} ${W + 40},${H}`} fill={col} />;
};

const Sky: React.FC<{ id: string; top: string; mid: string; low: string; t: number; sun?: boolean }> = ({ id, top, mid, low, t, sun = true }) => (
  <g>
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={top} />
        <stop offset="0.55" stopColor={mid} />
        <stop offset="1" stopColor={low} />
      </linearGradient>
      <radialGradient id={id + "s"}>
        <stop offset="0" stopColor="#fff3c4" stopOpacity="1" />
        <stop offset="0.35" stopColor="#ffd58a" stopOpacity="0.6" />
        <stop offset="1" stopColor="#ffb060" stopOpacity="0" />
      </radialGradient>
    </defs>
    <rect x={-W} y={-H} width={W * 3} height={H * 3} fill={`url(#${id})`} />
    {sun && <circle cx={1450} cy={560} r={260} fill={`url(#${id}s)`} />}
    {sun && <circle cx={1450} cy={560} r={58} fill="#fff0bb" />}
    {[0, 1, 2, 3, 4].map((i) => (
      <ellipse key={i} cx={((i * 520 + t * (0.25 + i * 0.05)) % (W + 600)) - 300} cy={150 + i * 55} rx={260 + i * 20} ry={34 + i * 6} fill="#4a3d58" opacity={0.5} />
    ))}
  </g>
);

const Ground: React.FC<{ camX: number; light: string; dark: string }> = ({ camX, light, dark }) => (
  <g>
    <defs>
      <linearGradient id="gnd" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={light} />
        <stop offset="1" stopColor={dark} />
      </linearGradient>
    </defs>
    <rect x={-W} y={GROUND} width={W * 4} height={H} fill="url(#gnd)" />
    {Array.from({ length: 46 }).map((_, i) => {
      const x = ((i * 137 + 40) % 2600) - camX;
      return <ellipse key={i} cx={x} cy={GROUND + 30 + (i % 7) * 26} rx={6 + (i % 4) * 3} ry={3 + (i % 3)} fill={dark} opacity={0.5} />;
    })}
  </g>
);

const Trunk: React.FC<{ x: number; top: number; w: number }> = ({ x, top, w }) => (
  <g>
    <rect x={x - w / 2} y={top} width={w} height={GROUND + 20 - top} fill="#7a4a2a" stroke="#3a2212" strokeWidth={4} />
    {[0.2, 0.45, 0.7].map((k) => (
      <path key={k} d={`M${x - w * 0.25},${top + (GROUND - top) * k} q${w * 0.2},-30 ${w * 0.1},-70`} stroke="#4d2e18" strokeWidth={4} fill="none" />
    ))}
  </g>
);

const Stones: React.FC<{ cx: number; cy: number; rx: number; ry: number; n: number }> = ({ cx, cy, rx, ry, n }) => (
  <g>
    {Array.from({ length: n }).map((_, i) => {
      const a = (i / n) * Math.PI * 2;
      const x = cx + Math.cos(a) * rx;
      const y = cy + Math.sin(a) * ry;
      return <ellipse key={i} cx={x} cy={y} rx={34} ry={22} fill={i % 2 ? "#8d8579" : "#a39a8b"} stroke="#3f3a33" strokeWidth={4} />;
    })}
  </g>
);

const Bucket: React.FC<{ cx: number; top: number; s: number }> = ({ cx, top, s }) => (
  <g stroke="#141414" strokeWidth={3} strokeLinejoin="round">
    <path d={`M${cx - 20 * s},${top + 2 * s} Q${cx},${top - 28 * s} ${cx + 20 * s},${top + 2 * s}`} fill="none" strokeWidth={4} />
    <polygon points={`${cx - 22 * s},${top} ${cx + 22 * s},${top} ${cx + 17 * s},${top + 36 * s} ${cx - 17 * s},${top + 36 * s}`} fill="#4b6b3a" />
    <ellipse cx={cx} cy={top} rx={22 * s} ry={5 * s} fill="#6fa6c4" />
  </g>
);

const Fade: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(f, [0, 10, dur - 10, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), background: "#07090c" }}>{children}</AbsoluteFill>;
};

const Label: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 40, bottom: 36, fontFamily: "Arial, sans-serif", fontSize: 30, fontWeight: 700, color: "#fff", background: "rgba(20,20,20,0.6)", padding: "8px 18px", borderRadius: 10, opacity: interpolate(f, [8, 20, 120, 135], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
      {text}
    </div>
  );
};

// ------------------------------------------------------------------ act components
const Act1: React.FC = () => {
  const t = useCurrentFrame();
  const dp = evalPose(dadTL, {}, t, DAD_S, dadReach1);
  const sp = evalPose(sonTL1, {}, t, SON_S);
  const dF = dadTL.facing(t);
  const k = sstep((t - (M1.tieStart + 14)) / 56);
  const tarp = `${230},${520} ${TREE_R - 4},${lerp(700, 560, k)} ${TREE_R - 40},${lerp(760, 650, k)} ${270},${640}`;
  const carried = t < M1.down;
  const cheer = t >= M1.tied && t < M1.tied + 50;
  return (
    <>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <Sky id="a1" top="#5a5072" mid="#d77f4d" low="#f6b768" t={t} />
        <Hills camX={0} par={0.05} base={640} amp={50} col="#58597a" ph={0.4} />
        <Hills camX={0} par={0.1} base={700} amp={40} col="#43506a" ph={1.7} />
        <PineRow camX={0} par={0.2} seed="a1f" n={30} base={760} h={[170, 260]} col="#2d4b3c" span={2200} />
        <PineRow camX={0} par={0.4} seed="a1m" n={18} base={800} h={[260, 380]} col="#1f3a2e" span={2200} />
        <Ground camX={0} light="#c0834a" dark="#8a5a31" />
        <Trunk x={220} top={120} w={80} />
        <Trunk x={TREE_R} top={120} w={86} />
        {/* table, benches, packs */}
        <g stroke="#2a1809" strokeWidth={4} strokeLinejoin="round">
          <rect x={470} y={742} width={430} height={22} fill="#8a5a2c" />
          <rect x={500} y={764} width={22} height={88} fill="#6e4521" />
          <rect x={850} y={764} width={22} height={88} fill="#6e4521" />
          <rect x={455} y={808} width={460} height={16} fill="#7d4f26" />
          <rect x={150} y={760} width={70} height={92} rx={14} fill="#3b6b4a" />
          <rect x={235} y={780} width={60} height={72} rx={14} fill="#c26a1e" />
        </g>
        <polygon points={tarp} fill="#e6c48a" stroke="#6a4f2a" strokeWidth={5} strokeLinejoin="round" />
        <Stones cx={RING_X + 40} cy={GROUND + 26} rx={130} ry={34} n={10} />
        {!carried && <Bucket cx={BUCKET_X} top={GROUND - 4} s={1.3} />}
        <g stroke="#141414" strokeWidth={3}>
          <line x1={BUCKET_X + 90} y1={GROUND + 6} x2={BUCKET_X + 118} y2={GROUND - 70} stroke="#8a6a3a" strokeWidth={8} />
        </g>
        <Puppet pose={sp} facing={sonTL1.facing(t)} scale={SON_S} look={SON_LOOK} expr={cheer ? "cheer" : "smile"} />
        <Puppet pose={dp} facing={dF} scale={DAD_S} look={DAD_LOOK} expr={t > M1.tied ? "smile" : "flat"}>
          {(j) => (carried ? <Bucket cx={j.rHand[0]} top={j.rHand[1] + 4} s={1.3} /> : null)}
        </Puppet>
      </svg>
      <Label text="Act 1: walk, carry, set down, tie a rope, cheer" />
    </>
  );
};

const Bundle: React.FC<{ a: V2; b: V2; n: number; s: number }> = ({ a, b, n, s }) => {
  const mx = (a[0] + b[0]) / 2;
  const my = (a[1] + b[1]) / 2;
  return (
    <g strokeLinecap="round">
      {Array.from({ length: n }).map((_, i) => {
        const ang = (-28 + i * 14 + (i % 2) * 4) * (Math.PI / 180);
        const len = 82 * s;
        const x2 = mx + Math.cos(ang) * len;
        const y2 = my + Math.sin(ang) * len - 10 * s;
        const x1 = mx - Math.cos(ang) * len * 0.35;
        const y1 = my - Math.sin(ang) * len * 0.35 - 6 * s;
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#141414" strokeWidth={10 * s} />
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={i % 2 ? "#6b4a2a" : "#7d5a35"} strokeWidth={6 * s} />
          </g>
        );
      })}
    </g>
  );
};

const Act2: React.FC = () => {
  const t = useCurrentFrame();
  const sp = evalPose(sonTL2, {}, t, SON_S, sonReach2);
  const camX = Math.max(0, Math.min(2300, sp.x - 650));
  const picked = [0, 1, 2].map((i) => t >= M2["pick" + i] + 6);
  const count = picked.filter(Boolean).length;
  return (
    <>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <Sky id="a2" top="#3d3a55" mid="#a8623f" low="#e0a05c" t={t} sun={false} />
        <Hills camX={camX} par={0.05} base={600} amp={55} col="#3f4260" ph={0.9} />
        <PineRow camX={camX} par={0.2} seed="a2f" n={40} base={740} h={[220, 340]} col="#243f33" span={4400} />
        <PineRow camX={camX} par={0.45} seed="a2m" n={30} base={800} h={[320, 480]} col="#1a3228" span={4600} />
        <Ground camX={camX} light="#8c5d34" dark="#5e3a1e" />
        <PineRow camX={camX} par={0.8} seed="a2n" n={14} base={GROUND + 10} h={[520, 700]} col="#12261d" span={5000} />
        <g transform={`translate(${-camX} 0)`}>
          {BRANCH_X.map((x, i) =>
            picked[i] ? null : (
              <g key={i} strokeLinecap="round">
                <line x1={x - 50} y1={GROUND - 6} x2={x + 60} y2={GROUND - 20} stroke="#141414" strokeWidth={11} />
                <line x1={x - 50} y1={GROUND - 6} x2={x + 60} y2={GROUND - 20} stroke="#7d5a35" strokeWidth={7} />
              </g>
            ),
          )}
          <Puppet pose={{ ...sp }} facing={sonTL2.facing(t)} scale={SON_S} look={SON_LOOK} expr="smile">
            {(j) => (count > 0 ? <Bundle a={j.lHand} b={j.rHand} n={count} s={SON_S} /> : null)}
          </Puppet>
        </g>
        <rect width={W} height={H} fill="#10202a" opacity={0.22} />
        <FallingLeaves f={t} seed="a2" count={16} opacity={0.9} colors={["#b8651b", "#d08a2e", "#8f4a14", "#c9a227"]} />
      </svg>
      <Label text="Act 2: walk, bend and pick up, carry a growing load, turn back" />
    </>
  );
};

const Smoke: React.FC<{ x: number; y: number; u: number }> = ({ x, y, u }) => {
  if (u < 0 || u > 110) return null;
  return (
    <g filter="url(#bl)">
      {[0, 1, 2, 3, 4].map((i) => {
        const age = u - i * 12;
        if (age < 0) return null;
        const yy = y - age * 2.4;
        const xx = x + Math.sin(age * 0.09 + i) * (12 + age * 0.4);
        return <circle key={i} cx={xx} cy={yy} r={14 + age * 0.45} fill="#d6d7db" opacity={Math.max(0, 0.85 - age / 130)} />;
      })}
    </g>
  );
};

const Act3: React.FC = () => {
  const t = useCurrentFrame();
  const sp = evalPose(sonTL3, {}, t, SON_S, sonReach3);
  const carrying = t < M3.drop;
  const think = t >= M3.think - 8;
  let flame = 0; // match flame
  let base = 0; // flare at the cone
  let smokeU = -1;
  [0, 1, 2].forEach((i) => {
    const u = t - M3["s" + i];
    if (u >= 18 && u < 40) flame = 1;
    if (u >= 36 && u < 58) base = Math.max(base, 1 - (u - 36) / 22);
    if (u >= 40) smokeU = Math.max(smokeU, u - 40);
  });
  const apex: V2 = [CONE_X, 600];
  const sticks = Array.from({ length: 13 }).map((_, i) => {
    const k = i / 12 - 0.5;
    return { x1: CONE_X + k * 250, y1: GROUND - 18 + (i % 3) * 4, x2: apex[0] + k * 14, y2: apex[1] + (i % 4) * 8 };
  });
  const z = 1.4;
  return (
    <>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <defs>
          <filter id="bl">
            <feGaussianBlur stdDeviation="7" />
          </filter>
        </defs>
        <g transform={`translate(${W / 2} ${H / 2}) scale(${z}) translate(${-960} ${-690})`}>
          <Sky id="a3" top="#4a4268" mid="#d77f4d" low="#f6b768" t={t} />
          <Hills camX={0} par={0.05} base={640} amp={50} col="#58597a" ph={0.4} />
          <PineRow camX={0} par={0.2} seed="a3f" n={30} base={760} h={[170, 260]} col="#2d4b3c" span={2200} />
          <PineRow camX={0} par={0.4} seed="a3m" n={18} base={800} h={[260, 380]} col="#1f3a2e" span={2200} />
          <Ground camX={0} light="#c0834a" dark="#8a5a31" />
          <Stones cx={CONE_X} cy={GROUND + 4} rx={170} ry={34} n={12} />
          {sticks.map((s, i) => (
            <g key={i} strokeLinecap="round">
              <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke="#141414" strokeWidth={12} />
              <line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={i % 2 ? "#5e4126" : "#6f4d2c"} strokeWidth={7.5} />
            </g>
          ))}
          <ellipse cx={MATCH_T[0] + 6} cy={GROUND - 18} rx={42} ry={14} fill="#8a6a3a" stroke="#141414" strokeWidth={3} />
          {base > 0 && (
            <g opacity={base}>
              <Fire f={t} x={MATCH_T[0] + 6} y={GROUND - 22} s={0.95 * (0.6 + 0.4 * base)} seed="cone" />
            </g>
          )}
          <Smoke x={MATCH_T[0] + 20} y={GROUND - 40} u={smokeU} />
          <Puppet pose={sp} facing={1} scale={SON_S} look={SON_LOOK} expr={think ? "frown" : "flat"}>
            {(j) => (
              <>
                {carrying && <Bundle a={j.lHand} b={j.rHand} n={3} s={SON_S} />}
                {t >= M3.drop + 16 && (
                  <g stroke="#141414" strokeWidth={3}>
                    <rect x={j.lHand[0] - 14} y={j.lHand[1] - 16} width={28} height={20} rx={3} fill="#c9a55a" />
                  </g>
                )}
                {t >= M3.drop + 30 && !think && (
                  <g>
                    <line x1={j.rHand[0]} y1={j.rHand[1]} x2={j.rHand[0] + 22} y2={j.rHand[1] - 8} stroke="#141414" strokeWidth={6} strokeLinecap="round" />
                    <line x1={j.rHand[0]} y1={j.rHand[1]} x2={j.rHand[0] + 22} y2={j.rHand[1] - 8} stroke="#d9b06a" strokeWidth={3} strokeLinecap="round" />
                    {flame > 0 && <Fire f={t} x={j.rHand[0] + 23} y={j.rHand[1] - 8} s={0.17} seed="m" embers={false} />}
                  </g>
                )}
              </>
            )}
          </Puppet>
        </g>
        <rect width={W} height={H} fill="#10202a" opacity={0.1} />
      </svg>
      <Label text="Act 3: walk, drop the load, kneel, strike a match three times, think" />
    </>
  );
};

// ------------------------------------------------------------------ video
export type VideoProps = { music: number; sfx: number };

export const Video: React.FC<VideoProps> = ({ music, sfx }) => (
  <AbsoluteFill style={{ background: "#07090c" }}>
    <Sequence from={0} durationInFrames={ACT1}>
      <Fade dur={ACT1}>
        <Act1 />
      </Fade>
    </Sequence>
    <Sequence from={OFF2} durationInFrames={ACT2}>
      <Fade dur={ACT2}>
        <Act2 />
      </Fade>
    </Sequence>
    <Sequence from={OFF3} durationInFrames={ACT3}>
      <Fade dur={ACT3}>
        <Act3 />
      </Fade>
    </Sequence>
    <Audio src={staticFile("pk-ep01/music.wav")} volume={(f) => music * interpolate(f, [0, 30, DURATION - 60, DURATION], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
    <Audio src={staticFile("pk-ep01/sfx/amb_forest.wav")} loop volume={(f) => 0.3 * sfx * interpolate(f, [0, 40, DURATION - 60, DURATION], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
    {EVENTS.filter((e) => e.vol > 0).map((e, k) => (
      <Sequence key={k} from={e.frame} durationInFrames={240}>
        <Audio src={staticFile(`pk-ep01/sfx/${e.name}.wav`)} volume={e.vol * sfx} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
