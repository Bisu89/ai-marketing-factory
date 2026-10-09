import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import { PRESET_COMPONENTS } from "./presets";
import { COLORS, FONTS } from "./theme";
import type { DocumentaryProps, Scene } from "./schema";

function SceneView({ scene, fade, first, grayscale }: { scene: Scene; fade: number; first: boolean; grayscale: boolean }) {
  const frame = useCurrentFrame();
  const Preset = PRESET_COMPONENTS[scene.preset];
  // Each scene fades in OVER the previous one (which keeps playing underneath for `fade`
  // frames), so a cut can never expose a black frame.
  const opacity = first || fade === 0 ? 1 : interpolate(frame, [0, fade], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity }}>
      <Preset scene={scene} grayscale={grayscale} />
    </AbsoluteFill>
  );
}

function Subtitles({ subtitles }: { subtitles: DocumentaryProps["subtitles"] }) {
  const frame = useCurrentFrame();
  const cur = subtitles.find((s) => frame >= s.startFrame && frame < s.endFrame);
  if (!cur) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 54 }}>
      <div
        style={{
          maxWidth: 1500,
          textAlign: "center",
          fontFamily: FONTS.sans,
          fontWeight: 700,
          fontSize: 46,
          lineHeight: 1.22,
          color: "#fff",
          padding: "8px 22px",
          background: "rgba(20, 17, 12, 0.62)",
          borderBottom: `5px solid ${COLORS.yellow}`,
        }}
      >
        {cur.text}
      </div>
    </AbsoluteFill>
  );
}

export const Documentary = (props: DocumentaryProps) => {
  const last = props.scenes.length - 1;
  return (
    <AbsoluteFill style={{ background: COLORS.paper }}>
      {props.scenes.map((scene, i) => (
        <Sequence
          key={scene.key}
          from={scene.startFrame}
          // overlap the next scene by the fade length so it can fade in over this one
          durationInFrames={scene.durationFrames + (i < last ? props.fadeFrames : 0)}
          layout="none"
        >
          <SceneView scene={scene} fade={props.fadeFrames} first={i === 0} grayscale={props.grayscale} />
        </Sequence>
      ))}
      {props.burnSubtitles && <Subtitles subtitles={props.subtitles} />}
    </AbsoluteFill>
  );
};
