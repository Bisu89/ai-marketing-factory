import React from "react";
import { COL } from "./fx";

// Side-view horse with a gallop cycle, rearing, and a saddle hook for a rider. Everything is in
// a local frame with the origin at the saddle (top of the back) and x pointing forward; the whole
// thing is flipped by `facing` and sized by `scale`.
//   <Horse f={f} x={x} ground={880} scale={0.95} amp={1} cloth="#f2f2f2">
//     {(sd) => <Hero f={f} who="officer" x={sd.x} ground={rideGround(sd, 0.9)} scale={0.9} stance={RIDE} ... />}
//   </Horse>

export const GALLOP = 0.42; // cycle speed in rad/frame (about 15 frames per stride)
export const HORSE_GROUND = 190; // saddle to hoof, unscaled

const rad = (d: number) => (d * Math.PI) / 180;
const dir = (a: number) => [Math.sin(rad(a)), Math.cos(rad(a))] as const; // 0 = down, + = forward
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export type Saddle = { x: number; y: number; tilt: number; s: number }; // world position of the saddle; tilt (deg, + = leaning forward-down) to rotate a rider with the horse

// ground value to give a Hero (cast.tsx) so its hip sits on the saddle
export const rideGround = (sd: Saddle, heroScale: number) => sd.y + 92.5 * heroScale;

const darken = (hex: string, k = 0.78) => {
  const n = parseInt(hex.slice(1), 16);
  const c = (v: number) => Math.round(v * k).toString(16).padStart(2, "0");
  return `#${c((n >> 16) & 255)}${c((n >> 8) & 255)}${c(n & 255)}`;
};

const SADDLE_X = -20; // the rider sits behind the withers, not on the neck
const UP = 62;
const LO = 66;

export const Horse: React.FC<{
  f: number;
  x: number;
  ground?: number; // y of the floor under the hooves
  scale?: number;
  facing?: 1 | -1;
  speed?: number; // stride speed in rad/frame (GALLOP by default)
  amp?: number; // 0 = standing, 1 = full gallop: animate it to start/stop
  rear?: number; // 0..1 rears up on the hind legs
  coat?: string;
  mane?: string;
  cloth?: string; // optional caparison draped over the body
  trim?: string;
  children?: (sd: Saddle) => React.ReactNode;
}> = ({ f, x, ground = 880, scale = 1, facing = 1, speed = GALLOP, amp = 1, rear = 0, coat = "#8a5a2b", mane = "#2b1b10", cloth, trim = COL.red, children }) => {
  const th = f * speed;
  const sw = (ph: number) => Math.sin(th + ph);
  const lf = (ph: number) => Math.max(0, Math.cos(th + ph));
  const frontA1 = (ph: number) => lerp(4 + amp * 36 * sw(ph), 62, rear);
  const frontA2 = (ph: number) => lerp(-amp * 75 * lf(ph), -85, rear);
  const hindA1 = (ph: number) => lerp(-5 + amp * 30 * sw(ph), -4, rear);
  const hindA2 = (ph: number) => lerp(-12 - amp * 55 * lf(ph), -12, rear);

  const bounce = -Math.abs(Math.sin(th)) * 7 * amp;
  const pitch = Math.sin(th + 0.8) * 3 * amp;
  const rearAng = -rear * 40;
  const nod = Math.sin(th * 2) * 4 * amp - rear * 12;

  const X = x;
  const Y = ground - HORSE_GROUND * scale;

  // saddle in world space: rotate (0,0) about the hind hooves by the rear angle, add the bounce, then flip/scale
  const a = rad(rearAng);
  const dx = SADDLE_X + 68; // saddle relative to the hind-hoof pivot (-68, HORSE_GROUND)
  const px = -68 + dx * Math.cos(a) + HORSE_GROUND * Math.sin(a);
  const py = HORSE_GROUND + dx * Math.sin(a) - HORSE_GROUND * Math.cos(a) + bounce;
  const saddle: Saddle = { x: X + scale * facing * px, y: Y + scale * py, tilt: rearAng + pitch, s: scale };

  const leg = (rx: number, a1: number, a2: number, col: string) => {
    const ry = 56;
    const [d1x, d1y] = dir(a1);
    const kx = rx + d1x * UP;
    const ky = ry + d1y * UP;
    const [d2x, d2y] = dir(a1 + a2);
    const fx = kx + d2x * LO;
    const fy = ky + d2y * LO;
    const round = { strokeLinecap: "round" as const, fill: "none" };
    return (
      <g>
        <line x1={rx} y1={ry} x2={kx} y2={ky} stroke={COL.ink} strokeWidth={32} {...round} />
        <line x1={kx} y1={ky} x2={fx} y2={fy} stroke={COL.ink} strokeWidth={22} {...round} />
        <line x1={rx} y1={ry} x2={kx} y2={ky} stroke={col} strokeWidth={24} {...round} />
        <line x1={kx} y1={ky} x2={fx} y2={fy} stroke={col} strokeWidth={14} {...round} />
        <ellipse cx={fx} cy={fy + 3} rx={10} ry={6} fill="#2a2a2a" transform={`rotate(${-(a1 + a2)} ${fx} ${fy})`} />
      </g>
    );
  };

  const far = darken(coat);
  const tailTipY = 90 - 55 * amp + Math.sin(th * 1.1) * 10;

  return (
    <g>
      <g transform={`translate(${X} ${Y}) scale(${scale * facing} ${scale})`}>
        <g transform={`translate(0 ${bounce})`}>
          <g transform={`rotate(${rearAng} -68 ${HORSE_GROUND})`}>
            {leg(-68, hindA1(0), hindA2(0), far)}
            {leg(66, frontA1(2.7), frontA2(2.7), far)}
            <g transform={`rotate(${pitch})`}>
              <path d={`M-98,8 C-125,12 -140,${40 - 30 * amp} ${-140 - 20 * amp},${tailTipY}`} stroke={COL.ink} strokeWidth={22} strokeLinecap="round" fill="none" />
              <path d={`M-98,8 C-125,12 -140,${40 - 30 * amp} ${-140 - 20 * amp},${tailTipY}`} stroke={mane} strokeWidth={14} strokeLinecap="round" fill="none" />
              <ellipse cx={0} cy={36} rx={104} ry={42} fill={coat} stroke={COL.ink} strokeWidth={6} />
              {cloth && (
                <>
                  <path
                    d="M-64,8 L70,8 L70,60 Q56,72 42,60 Q28,72 14,60 Q0,72 -14,60 Q-28,72 -42,60 Q-56,72 -64,60 Z"
                    fill={cloth}
                    stroke={COL.ink}
                    strokeWidth={5}
                    strokeLinejoin="round"
                  />
                  <line x1={-64} y1={16} x2={70} y2={16} stroke={trim} strokeWidth={8} />
                </>
              )}
              <polygon points="40,-8 118,-62 136,-34 84,50" fill={coat} stroke={COL.ink} strokeWidth={6} strokeLinejoin="round" />
              <line x1={44} y1={-12} x2={118} y2={-66} stroke={mane} strokeWidth={12} strokeLinecap="round" />
              <g transform={`translate(128 -50) rotate(${50 + nod})`}>
                <polygon points="-6,-12 2,-36 14,-14" fill={coat} stroke={COL.ink} strokeWidth={4} strokeLinejoin="round" />
                <ellipse cx={28} cy={0} rx={40} ry={20} fill={coat} stroke={COL.ink} strokeWidth={6} />
                <ellipse cx={60} cy={5} rx={14} ry={13} fill={darken(coat, 0.7)} stroke={COL.ink} strokeWidth={4} />
                <circle cx={14} cy={-6} r={4} fill={COL.ink} />
                <circle cx={15.5} cy={-7.5} r={1.4} fill="#fff" />
                <circle cx={64} cy={2} r={2} fill={COL.ink} />
              </g>
              <rect x={SADDLE_X - 24} y={-10} width={48} height={12} rx={5} fill="#5a3a1e" stroke={COL.ink} strokeWidth={4} />
            </g>
            {leg(-68, hindA1(0.6), hindA2(0.6), coat)}
            {leg(66, frontA1(3.3), frontA2(3.3), coat)}
          </g>
        </g>
      </g>
      {children?.(saddle)}
    </g>
  );
};
