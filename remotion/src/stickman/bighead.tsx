import React from "react";
import { COL, FONT } from "./fx";

// Upgraded stick-figure head: a big, expressive, detailed head on the existing poseable
// stick body. Pair it with Actor/Figure's `headless` prop and the children render prop:
//   <Actor headless f={f} keys={...} color={COL.orange}>
//     {(j) => <BigHead x={j.headC[0]} y={j.headC[1]} angle={headAngle(j)} emotion="worried" talk={talkCycle(f)} />}
//   </Actor>
// headAngle/Joints come from stick.tsx; the body stays fully poseable (walk/run/punch/...),
// only the head rendering is swapped.

export type Hair = "bun" | "short" | "bald" | "ponytail" | "long" | "none" | "kabuto" | "helmet" | "spiky" | "afro" | "kettle" | "bascinet";
export type Emotion = "neutral" | "angry" | "sad" | "happy" | "shock" | "worried" | "cry" | "smug" | "stern";
export type FaceShape = "round" | "oval" | "square";

// simple mouth-flap cycle for narration-synced talking: feed it the scene's frame while a
// cue is speaking (0 while silent) for a cheap but convincing "talking head" bounce.
export const talkCycle = (f: number, speed = 0.9) => Math.max(0, Math.sin(f * speed)) ** 1.5;

const BROW_SLOPE: Record<Emotion, number> = { neutral: 0, angry: 0.4, sad: -0.35, happy: 0, shock: -0.1, worried: -0.2, cry: -0.4, smug: 0.2, stern: 0.12 };

export const BigHead: React.FC<{
  x: number;
  y: number;
  angle?: number; // from headAngle(j) in stick.tsx; 0 = upright
  facing?: number;
  r?: number; // head radius — deliberately much bigger than the body's own head (R ≈ 24*scale)
  skin?: string;
  shape?: FaceShape;
  hair?: Hair;
  hairColor?: string;
  emotion?: Emotion;
  talk?: number; // 0..1 mouth openness (talkCycle(f) while speaking, 0 when silent)
  blink?: boolean;
  label?: string;
  eyes?: "round" | "dot"; // "dot" = two small dark dots, no white (quieter, for serious/period characters)
  crest?: string; // plume colour on a bascinet/kettle
}> = ({
  x,
  y,
  angle = 0,
  facing = 1,
  r = 72,
  skin = "#f0c9a0",
  shape = "round",
  hair = "short",
  hairColor = "#1a1a1a",
  emotion = "neutral",
  talk = 0,
  blink = false,
  label,
  eyes = "round",
  crest,
}) => {
  const slope = BROW_SLOPE[emotion] * r;
  const browY = -r * 0.32;
  const eyeY = -r * 0.08;
  const eyeDX = r * 0.32;
  const pupilR = r * (blink ? 0.02 : 0.1);
  const mouthY = r * 0.42;
  const mouthW = r * 0.34;
  const mouthOpen = r * 0.1 * Math.max(talk, emotion === "shock" ? 1.4 : emotion === "happy" ? 0.25 : emotion === "cry" ? 0.7 : 0);
  const downMouth = emotion === "sad" || emotion === "cry";
  const faceProps = { fill: skin, stroke: COL.ink, strokeWidth: r * 0.07 };
  // hair cap: `peak` = how far above the head's centre the top reaches (in r); the hairline sits at a fixed 0.55r
  const topHair = (peak: number) => `M${-r},${-r * 0.1} Q0,${r * (0.1 - 2 * peak)} ${r},${-r * 0.1} Q0,${-r} ${-r},${-r * 0.1} Z`;

  return (
    <g transform={`translate(${x} ${y}) rotate(${angle}) scale(${facing} 1)`}>
      {hair === "ponytail" && (
        <path d={`M${r * 0.5},${-r * 0.5} Q${r * 1.5},${r * 0.3} ${r * 0.9},${r * 1.6}`} stroke={hairColor} strokeWidth={r * 0.22} strokeLinecap="round" fill="none" />
      )}
      {hair === "long" && (
        <path
          d={`M${-r * 0.9},${-r * 0.2} Q${-r * 1.1},${r * 1.2} ${-r * 0.3},${r * 1.6} M${r * 0.9},${-r * 0.2} Q${r * 1.1},${r * 1.2} ${r * 0.3},${r * 1.6}`}
          stroke={hairColor}
          strokeWidth={r * 0.2}
          strokeLinecap="round"
          fill="none"
        />
      )}

      {hair === "afro" && <circle cx={0} cy={-r * 0.42} r={r * 1.32} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.05} />}

      {shape === "oval" ? (
        <ellipse cx={0} cy={r * 0.06} rx={r * 0.88} ry={r * 1.1} {...faceProps} />
      ) : shape === "square" ? (
        <rect x={-r} y={-r * 0.95} width={r * 2} height={r * 1.95} rx={r * 0.45} {...faceProps} />
      ) : (
        <circle cx={0} cy={0} r={r} {...faceProps} />
      )}

      {hair === "afro" && <path d={topHair(1.0)} fill={hairColor} />}
      {hair === "spiky" && (
        <>
          <path d={topHair(1.08)} fill={hairColor} />
          {[-2, -1, 0, 1, 2].map((k) => (
            <polygon
              key={k}
              points={`${k * r * 0.38 - r * 0.2},${-r * 0.7} ${k * r * 0.38},${-r * 1.5 + Math.abs(k) * r * 0.2} ${k * r * 0.38 + r * 0.2},${-r * 0.7}`}
              fill={hairColor}
              stroke={COL.ink}
              strokeWidth={r * 0.03}
              strokeLinejoin="round"
            />
          ))}
        </>
      )}
      {hair === "short" && <path d={topHair(1.12)} fill={hairColor} />}
      {hair === "bun" && (
        <>
          <path d={topHair(1.1)} fill={hairColor} />
          <circle cx={r * 0.1} cy={-r * 1.25} r={r * 0.3} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.05} />
          <rect x={-r * 0.05} y={-r * 1.05} width={r * 0.3} height={r * 0.12} rx={r * 0.06} fill={hairColor} />
        </>
      )}
      {hair === "ponytail" && <path d={topHair(1.12)} fill={hairColor} />}
      {hair === "long" && <path d={topHair(1.14)} fill={hairColor} />}
      {hair === "kabuto" && (
        <>
          <path d={topHair(1.2)} fill={hairColor} />
          <polygon points={`${-r * 0.06},${-r * 1.12} ${r * 0.55},${-r * 1.62} ${r * 0.14},${-r * 1.08}`} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.04} strokeLinejoin="round" />
          <rect x={-r * 1.08} y={-r * 0.3} width={r * 0.3} height={r * 0.6} rx={r * 0.08} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.03} />
          <rect x={r * 0.78} y={-r * 0.3} width={r * 0.3} height={r * 0.6} rx={r * 0.08} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.03} />
        </>
      )}
      {hair === "helmet" && (
        <>
          <path d={topHair(1.15)} fill={hairColor} />
          <rect x={-r * 1.1} y={-r * 0.18} width={r * 2.2} height={r * 0.15} rx={r * 0.07} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.03} />
        </>
      )}

      {hair === "kettle" && (
        <>
          <path d={`M${-r * 0.92},${-r * 0.46} Q0,${-r * 1.95} ${r * 0.92},${-r * 0.46} Z`} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.04} strokeLinejoin="round" />
          <path d={`M${-r * 1.3},${-r * 0.4} Q0,${-r * 0.55} ${r * 1.3},${-r * 0.4} L${r * 1.3},${-r * 0.5} Q0,${-r * 0.65} ${-r * 1.3},${-r * 0.5} Z`} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.04} strokeLinejoin="round" />
        </>
      )}
      {hair === "bascinet" && (
        <>
          <path d={`M${-r * 1.0},${-r * 0.3} Q${-r * 1.05},${-r * 1.55} 0,${-r * 1.75} Q${r * 1.05},${-r * 1.55} ${r * 1.0},${-r * 0.3} L${r * 0.92},${-r * 0.44} L${-r * 0.92},${-r * 0.44} Z`} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.04} strokeLinejoin="round" />
          <rect x={-r * 1.02} y={-r * 0.46} width={r * 0.2} height={r * 0.95} rx={r * 0.06} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.03} />
          <rect x={r * 0.82} y={-r * 0.46} width={r * 0.2} height={r * 0.95} rx={r * 0.06} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.03} />
          <rect x={-r * 0.05} y={-r * 0.46} width={r * 0.1} height={r * 0.52} fill={hairColor} stroke={COL.ink} strokeWidth={r * 0.025} />
          {crest && <path d={`M0,${-r * 1.72} Q${-r * 0.5},${-r * 2.2} ${-r * 1.0},${-r * 1.7}`} stroke={crest} strokeWidth={r * 0.2} strokeLinecap="round" fill="none" />}
        </>
      )}

      <line x1={-eyeDX - r * 0.16} y1={browY - slope} x2={-eyeDX + r * 0.16} y2={browY + slope} stroke={COL.ink} strokeWidth={r * 0.045} strokeLinecap="round" />
      <line x1={eyeDX - r * 0.16} y1={browY + slope} x2={eyeDX + r * 0.16} y2={browY - slope} stroke={COL.ink} strokeWidth={r * 0.045} strokeLinecap="round" />

      {blink ? (
        <>
          <line x1={-eyeDX - r * 0.12} y1={eyeY} x2={-eyeDX + r * 0.12} y2={eyeY} stroke={COL.ink} strokeWidth={r * 0.035} strokeLinecap="round" />
          <line x1={eyeDX - r * 0.12} y1={eyeY} x2={eyeDX + r * 0.12} y2={eyeY} stroke={COL.ink} strokeWidth={r * 0.035} strokeLinecap="round" />
        </>
      ) : (
        eyes === "dot" ? (
          <>
            <circle cx={-eyeDX} cy={eyeY} r={r * 0.065} fill={COL.ink} />
            <circle cx={eyeDX} cy={eyeY} r={r * 0.065} fill={COL.ink} />
          </>
        ) : (
        <>
          <ellipse cx={-eyeDX} cy={eyeY} rx={r * 0.13} ry={r * 0.16} fill="#fff" stroke={COL.ink} strokeWidth={r * 0.025} />
          <ellipse cx={eyeDX} cy={eyeY} rx={r * 0.13} ry={r * 0.16} fill="#fff" stroke={COL.ink} strokeWidth={r * 0.025} />
          <circle cx={-eyeDX} cy={eyeY + r * 0.02} r={pupilR} fill={COL.ink} />
          <circle cx={eyeDX} cy={eyeY + r * 0.02} r={pupilR} fill={COL.ink} />
          {emotion === "smug" &&
            [-eyeDX, eyeDX].map((ex) => (
              <g key={ex}>
                <rect x={ex - r * 0.15} y={eyeY - r * 0.18} width={r * 0.3} height={r * 0.18} fill={skin} />
                <line x1={ex - r * 0.15} y1={eyeY} x2={ex + r * 0.15} y2={eyeY} stroke={COL.ink} strokeWidth={r * 0.035} strokeLinecap="round" />
              </g>
            ))}
        </>
        )
      )}
      {emotion === "cry" &&
        [-eyeDX, eyeDX].map((ex) => (
          <path key={ex} d={`M${ex},${eyeY + r * 0.2} q${-r * 0.05},${r * 0.22} 0,${r * 0.42}`} stroke="#4aa3d8" strokeWidth={r * 0.07} strokeLinecap="round" fill="none" />
        ))}

      {mouthOpen > r * 0.02 ? (
        <path
          d={`M${-mouthW / 2},${mouthY} Q0,${mouthY + mouthOpen * (downMouth ? -1.6 : 1.6)} ${mouthW / 2},${mouthY} Q0,${mouthY + mouthOpen} ${-mouthW / 2},${mouthY} Z`}
          fill="#7a2e2e"
          stroke={COL.ink}
          strokeWidth={r * 0.03}
        />
      ) : (
        <path
          d={
            emotion === "smug"
              ? `M${-mouthW / 2},${mouthY} Q0,${mouthY + r * 0.04} ${mouthW / 2},${mouthY - r * 0.08}`
              : `M${-mouthW / 2},${mouthY} Q0,${mouthY + (emotion === "happy" ? r * 0.22 : downMouth ? -r * 0.1 : 0)} ${mouthW / 2},${mouthY}`
          }
          fill="none"
          stroke={COL.ink}
          strokeWidth={r * 0.045}
          strokeLinecap="round"
        />
      )}

      {label && (
        <text
          x={0}
          y={-r * 1.5}
          textAnchor="middle"
          fontFamily={FONT.title}
          fontWeight={800}
          fontSize={r * 0.32}
          fill={COL.ink}
          stroke="#fafaf7"
          strokeWidth={r * 0.08}
          paintOrder="stroke"
        >
          {label}
        </text>
      )}
    </g>
  );
};
