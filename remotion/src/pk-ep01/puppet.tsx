import React from "react";
import { headAngle, solve } from "../stickman/stick";
import type { Joints, Pose } from "../stickman/stick";

// Cartoon "puppet" drawn on the stickman engine's skeleton (stick.tsx `solve`): thick outlined limbs, jacket,
// trousers, shoes, round head, cap/beanie. Same poses, IK and moves as the stick figures; only the drawing differs.

export type Look = { skin: string; jacket: string; pants: string; shoe: string; hat: "cap" | "beanie"; hatColor: string };
export const DAD_LOOK: Look = { skin: "#f6d3b3", jacket: "#2f5d3a", pants: "#a89868", shoe: "#5a3a1e", hat: "cap", hatColor: "#6b6f75" };
export const SON_LOOK: Look = { skin: "#f6d3b3", jacket: "#e8731a", pants: "#3f6fa6", shoe: "#b8bcc2", hat: "beanie", hatColor: "#f2b705" };

const OUT = "#141414";
const shade = (hex: string, k: number) => {
  const n = parseInt(hex.slice(1), 16);
  const c = (v: number) => Math.round(Math.max(0, Math.min(255, v * k)));
  return `#${[(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => c(v).toString(16).padStart(2, "0")).join("")}`;
};

type V = [number, number];
const pts = (...a: V[]) => a.map((v) => v.join(",")).join(" ");

// one limb chain drawn as outline then fill, so the joint between the two segments has no seam
const Chain: React.FC<{ p: V[]; w: number; color: string; line: number }> = ({ p, w, color, line }) => (
  <g strokeLinecap="round" strokeLinejoin="round" fill="none">
    <polyline points={pts(...p)} stroke={OUT} strokeWidth={w + line * 2} />
    <polyline points={pts(...p)} stroke={color} strokeWidth={w} />
  </g>
);

export type Expr = "smile" | "frown" | "flat" | "cheer";

export const Puppet: React.FC<{
  pose: Pose;
  facing: 1 | -1;
  scale: number;
  look: Look;
  expr?: Expr;
  mouth?: number; // 0..1 open
  children?: (j: Joints, shoulder: V) => React.ReactNode;
}> = ({ pose, facing, scale: s, look, expr = "smile", mouth = 0, children }) => {
  const j = solve(pose, s, facing);
  const sh: V = [j.hip[0] + 0.92 * (j.neck[0] - j.hip[0]), j.hip[1] + 0.92 * (j.neck[1] - j.hip[1])];
  const line = 3.2 * s;
  const farJ = shade(look.jacket, 0.78);
  const farP = shade(look.pants, 0.78);
  const R = j.headR;
  const ang = headAngle(j);
  const hand = (p: V) => <circle cx={p[0]} cy={p[1]} r={9 * s} fill={look.skin} stroke={OUT} strokeWidth={line} />;
  const shoe = (f: V, c: string) => (
    <ellipse cx={f[0] + facing * 7 * s} cy={f[1] - 2 * s} rx={15 * s} ry={8.5 * s} fill={c} stroke={OUT} strokeWidth={line} />
  );
  const H = 1.3 * R; // head radius
  const cy = -0.25 * R; // head centre (local, up = negative)
  const ex = [0.4 * R, 0.85 * R];
  const eyeY = cy - 0.1 * R;
  const mY = cy + 0.5 * H;
  return (
    <g>
      {/* far arm and far leg */}
      <Chain p={[sh, j.lElbow, j.lHand]} w={14 * s} color={farJ} line={line} />
      {hand(j.lHand)}
      <Chain p={[j.hip, j.lKnee, j.lFoot]} w={18 * s} color={farP} line={line} />
      {shoe(j.lFoot, shade(look.shoe, 0.8))}
      {/* torso */}
      <Chain p={[j.neck, j.hip]} w={38 * s} color={look.jacket} line={line} />
      {/* near leg */}
      <Chain p={[j.hip, j.rKnee, j.rFoot]} w={18 * s} color={look.pants} line={line} />
      {shoe(j.rFoot, look.shoe)}
      {/* head */}
      <g transform={`translate(${j.headC[0]} ${j.headC[1]}) rotate(${ang}) scale(${facing} 1)`}>
        <circle cx={0} cy={cy} r={H} fill={look.skin} stroke={OUT} strokeWidth={line * 1.2} />
        {ex.map((x, i) => (
          <ellipse key={i} cx={x} cy={eyeY} rx={3.4 * s} ry={4.4 * s} fill={OUT} />
        ))}
        {expr === "smile" && mouth < 0.1 && <path d={`M${0.35 * R},${mY} Q${0.75 * R},${mY + 0.45 * R} ${1.15 * R},${mY}`} fill="none" stroke={OUT} strokeWidth={2.8 * s} strokeLinecap="round" />}
        {expr === "frown" && mouth < 0.1 && <path d={`M${0.35 * R},${mY + 0.3 * R} Q${0.75 * R},${mY - 0.15 * R} ${1.15 * R},${mY + 0.3 * R}`} fill="none" stroke={OUT} strokeWidth={2.8 * s} strokeLinecap="round" />}
        {expr === "flat" && mouth < 0.1 && <line x1={0.4 * R} y1={mY + 0.1 * R} x2={1.1 * R} y2={mY + 0.1 * R} stroke={OUT} strokeWidth={2.8 * s} strokeLinecap="round" />}
        {expr === "cheer" && <path d={`M${0.3 * R},${mY - 0.1 * R} Q${0.75 * R},${mY + 0.9 * R} ${1.2 * R},${mY - 0.1 * R} Z`} fill="#5a1a1a" stroke={OUT} strokeWidth={2.4 * s} strokeLinejoin="round" />}
        {mouth >= 0.1 && <ellipse cx={0.75 * R} cy={mY + 0.15 * R} rx={0.32 * R} ry={0.12 * R + 0.34 * R * mouth} fill="#5a1a1a" stroke={OUT} strokeWidth={2.2 * s} />}
        {look.hat === "cap" ? (
          <g stroke={OUT} strokeWidth={line} strokeLinejoin="round">
            <path d={`M${-H * 1.04},${cy - 0.1 * H} A${H * 1.04},${H * 1.05} 0 0 1 ${H * 1.04},${cy - 0.1 * H} Z`} fill={look.hatColor} />
            <rect x={0.2 * H} y={cy - 0.28 * H} width={1.2 * H} height={0.2 * H} rx={0.1 * H} fill={shade(look.hatColor, 0.85)} />
          </g>
        ) : (
          <g stroke={OUT} strokeWidth={line} strokeLinejoin="round">
            <path d={`M${-H * 1.08},${cy - 0.18 * H} A${H * 1.08},${H * 1.12} 0 0 1 ${H * 1.08},${cy - 0.18 * H} Z`} fill={look.hatColor} />
            <rect x={-H * 1.1} y={cy - 0.34 * H} width={H * 2.2} height={0.3 * H} rx={0.1 * H} fill={shade(look.hatColor, 0.92)} />
            <circle cx={0} cy={cy - H * 1.18} r={0.2 * H} fill={look.hatColor} />
          </g>
        )}
      </g>
      {/* near arm */}
      <Chain p={[sh, j.rElbow, j.rHand]} w={14 * s} color={look.jacket} line={line} />
      {hand(j.rHand)}
      {children?.(j, sh)}
    </g>
  );
};
