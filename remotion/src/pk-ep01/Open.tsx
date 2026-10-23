import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Captions } from "../stickman/common";
import { PkKenBurns } from "./PkKenBurns";
import { DURATION, LINES, SFX, SHOTS } from "./data";

// PACKED LIGHT ep1, opening test cut (content-prompts/packed_light/ep01_open_test.csv).
// Pictures + camera move + light fx, three voices (narrator, dad, son), synthesized SFX and a soft pad.
// Timing comes from data.ts (generated from the real voice-line durations), not hand-set.
export { DURATION };

const ASSETS = "pk-ep01";
const OVERLAP = 12;
const starts = SHOTS.map((s, i) => (i === 0 ? 0 : s.from - Math.floor(OVERLAP / 2)));
const endOf = (i: number) => (i + 1 < SHOTS.length ? starts[i + 1] + OVERLAP : DURATION);

const clampX = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const duck = (f: number) => {
  let g = 1;
  for (const l of LINES) {
    if (f < l.from - 10) break;
    g = Math.min(g, interpolate(f, [l.from - 8, l.from, l.to, l.to + 10], [1, 0.35, 0.35, 1], clampX));
  }
  return g;
};

// painted-on text for the notice board (the picture itself has no writing)
const Sign: React.FC = () => (
  <div
    style={{
      position: "absolute",
      left: 252,
      top: 405,
      width: 360,
      textAlign: "center",
      whiteSpace: "nowrap",
      fontFamily: "Arial Black, Arial, sans-serif",
      fontWeight: 900,
      fontSize: 19,
      lineHeight: 1.45,
      color: "#3b2a1a",
      mixBlendMode: "multiply",
      opacity: 0.85,
      letterSpacing: 1,
    }}
  >
    FIRES IN RINGS ONLY
    <br />
    DEAD AND DOWN WOOD ONLY
  </div>
);

const FadeOut: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: "#07090c", opacity: interpolate(f, [DURATION - 24, DURATION], [0, 1], clampX), pointerEvents: "none" }} />;
};

export type VideoProps ={ music: number; sfx: number; voice: number; captions: boolean };

export const Video: React.FC<VideoProps> = ({ music, sfx, voice, captions }) => (
  <AbsoluteFill style={{ background: "#07090c" }}>
    <Audio
      src={staticFile(`${ASSETS}/music.wav`)}
      volume={(f) => music * duck(f) * interpolate(f, [0, 30, DURATION - 60, DURATION], [0, 1, 1, 0], clampX)}
    />
    <Audio
      src={staticFile(`${ASSETS}/sfx/amb_forest.wav`)}
      loop
      volume={(f) => 0.3 * sfx * interpolate(f, [0, 40, DURATION - 60, DURATION], [0, 1, 1, 0], clampX)}
    />

    {SHOTS.map((s, i) => {
      const from = starts[i];
      const dur = endOf(i) - from;
      return (
        <Sequence key={s.n} from={from} durationInFrames={dur}>
          <PkKenBurns src={s.image} dur={dur} motion={s.motion} fx={s.fx} fade={i === 0 ? 1 : OVERLAP} seed={s.image} n={s.n} overlay={s.n === 2 ? <Sign /> : undefined} />
        </Sequence>
      );
    })}

    {LINES.map((l, k) => (
      <Sequence key={"v" + k} from={l.from} durationInFrames={l.to - l.from + 12}>
        <Audio src={staticFile(l.file)} volume={voice} />
      </Sequence>
    ))}

    {SFX.map((e, k) => (
      <Sequence key={"s" + k} from={e.frame} durationInFrames={240}>
        <Audio src={staticFile(`${ASSETS}/sfx/${e.name}.wav`)} volume={e.vol * sfx} />
      </Sequence>
    ))}

    {captions && <Captions cues={LINES.map((l) => ({ startFrame: l.from, endFrame: l.to + 6, text: l.text }))} bottom={64} size={44} />}

    <FadeOut />
  </AbsoluteFill>
);
