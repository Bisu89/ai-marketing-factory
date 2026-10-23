import React from "react";
import { Actor, addPose, groundY, headAngle, idle } from "./stick";
import type { Joints, Pose } from "./stick";
import { BigHead, talkCycle } from "./bighead";
import type { Emotion, FaceShape, Hair } from "./bighead";
import { Outfit } from "./outfit";
import type { OutfitType } from "./outfit";
import { COL } from "./fx";
import { compose } from "./moves";
import type { MoveFn } from "./moves";

// Ready-made characters: a preset bundles head shape, hair/headwear, skin, outfit and a default
// mood, and <Hero> assembles head + black stick body + outfit + moves in one component:
//   <Hero f={f} who="samurai" x={500} emotion="worried" talking moves={[walkTo(0, 60, 900), bow(66)]} />

export const SKIN = { pale: "#fbe3cf", light: "#f6d3b3", olive: "#d6a878", tan: "#e3b48a", brown: "#b9835a", dark: "#7a4e32" };

export type Preset = {
  hair: Hair;
  hairColor?: string;
  skin?: string;
  shape?: FaceShape;
  outfit?: OutfitType;
  outfitColor?: string;
  trim?: string;
  scale?: number; // relative size (a kid is smaller)
  emotion?: Emotion; // resting mood
  head?: number; // head size multiplier (default 1; 0.8 = 20% smaller, for sober/period characters)
  eyes?: "round" | "dot"; // "dot" = small dark dots instead of white eyes
  crest?: string; // plume colour for bascinet/kettle
};

export const PRESETS = {
  hero: { hair: "short", hairColor: "#2a1a0a", shape: "round", skin: SKIN.light },
  samurai: { hair: "kabuto", hairColor: "#2a2a2a", shape: "square", skin: SKIN.tan, outfit: "samurai" },
  ronin: { hair: "bun", hairColor: "#1a1a1a", shape: "square", skin: SKIN.tan, outfit: "samurai", outfitColor: "#6b5a45", trim: "#8a1f1f" },
  monk: { hair: "bald", shape: "round", skin: SKIN.tan, outfit: "samurai", outfitColor: "#c9702a", trim: "#7a3b1d" },
  soldier: { hair: "helmet", hairColor: "#4a5a3a", shape: "square", skin: SKIN.light, outfit: "soldier" },
  officer: { hair: "helmet", hairColor: "#2a3a5a", shape: "oval", skin: SKIN.pale, outfit: "soldier", outfitColor: "#2a3a5a", trim: "#c9a227" },
  villain: { hair: "bald", shape: "square", skin: SKIN.olive, outfit: "soldier", outfitColor: "#1f1f1f", trim: "#8a1f1f", emotion: "angry" },
  grandma: { hair: "bun", hairColor: "#d6d6d6", shape: "round", skin: SKIN.pale, scale: 0.95 },
  kid: { hair: "short", hairColor: "#6b3a1a", shape: "round", skin: SKIN.light, scale: 0.7 },
  punk: { hair: "spiky", hairColor: "#2fa84f", shape: "oval", skin: SKIN.light },
  hippie: { hair: "afro", hairColor: "#3a2414", shape: "round", skin: SKIN.brown },
  lady: { hair: "long", hairColor: "#7a3b1d", shape: "oval", skin: SKIN.light },
  athlete: { hair: "ponytail", hairColor: "#1a1a1a", shape: "oval", skin: SKIN.tan },
} satisfies Record<string, Preset>;

export type PresetName = keyof typeof PRESETS;

export const Hero: React.FC<{
  f: number;
  who: PresetName | Preset;
  x: number;
  ground?: number; // y of the floor under the feet (default 852)
  scale?: number;
  facing?: 1 | -1;
  emotion?: Emotion | ((f: number) => Emotion); // a function lets the mood change over time
  talking?: boolean | ((f: number) => boolean); // true = mouth flaps; a function follows your cues
  moves?: MoveFn[];
  stance?: Partial<Pose>; // resting pose merged into the start pose (e.g. a seated riding stance)
  mod?: (t: number, p: Pose) => Pose; // extra procedural motion, applied after the moves
  held?: (j: Joints, f: number) => React.ReactNode; // draw something in the hands (Sword, Lance...)
  label?: string;
  color?: string; // body stroke (black by default, the recommended look)
  trails?: boolean;
  seed?: number; // varies idle breathing/blinking between characters on screen
}> = ({ f, who, x, ground = 852, scale = 1.3, facing = 1, emotion, talking = false, moves, stance, mod: extraMod, held, label, color = COL.ink, trails = false, seed = 0 }) => {
  const p: Preset = typeof who === "string" ? PRESETS[who] : who;
  const s = scale * (p.scale ?? 1);
  const gy = groundY(s, ground);
  const m = moves ? compose({ gy, x, s }, moves, facing) : null;
  const dirAt = (t: number): 1 | -1 => (m ? m.facing(t) : facing);
  const emo = typeof emotion === "function" ? emotion(f) : emotion ?? p.emotion ?? "neutral";
  const talk = typeof talking === "function" ? talking(f) : talking;
  const outfit = p.outfit ?? "none";

  return (
    <Actor
      f={f}
      headless
      color={color}
      scale={s}
      base={{ x, y: gy, ...stance }}
      keys={[{ f: 0, p: { x, y: gy, ...stance } }, ...(m ? m.keys : [])]}
      facing={dirAt}
      trails={trails}
      mod={(t, pp) => {
        const q = m ? m.mod(t, pp) : pp;
        return addPose(extraMod ? extraMod(t, q) : q, idle(t, seed));
      }}
      behind={(j) => (outfit === "none" ? null : <Outfit j={j} scale={s} type={outfit} color={p.outfitColor} trim={p.trim} />)}
    >
      {(j) => (
        <>
        <BigHead
          x={j.headC[0]}
          y={j.headC[1]}
          angle={headAngle(j)}
          facing={-dirAt(f)}
          r={55 * s * (p.head ?? 1)}
          eyes={p.eyes}
          crest={p.crest}
          skin={p.skin}
          shape={p.shape}
          hair={p.hair}
          hairColor={p.hairColor}
          emotion={emo}
          talk={talk ? talkCycle(f) : 0}
          blink={(f + seed * 17) % 90 < 4}
          label={label}
        />
        {held ? held(j, f) : null}
        </>
      )}
    </Actor>
  );
};
