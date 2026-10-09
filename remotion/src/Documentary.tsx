import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import { CINE_COMPONENTS, CineSubtitles } from "./cinematic";
import { POSTER_COMPONENTS, PosterSubtitles } from "./poster";
import { PRESET_COMPONENTS } from "./presets";
import { COLORS, FONTS } from "./theme";
import type { DocumentaryProps, Scene } from "./schema";

function SceneView({ scene, fade, first, grayscale, theme }: { scene: Scene; fade: number; first: boolean; grayscale: boolean; theme: DocumentaryProps["theme"] }) {
  const frame = useCurrentFrame();
  const Preset = (theme === "cinematic" ? CINE_COMPONENTS : theme === "poster" ? POSTER_COMPONENTS : PRESET_COMPONENTS)[scene.preset];
  // Each scene fades in OVER the previous one (which keeps playing underneath for `fade`
  // frames), so a cut can never expose a black frame.
  const opacity = first || fade === 0 ? 1 : interpolate(frame, [0, fade], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity }}>
      <Preset scene={scene} grayscale={grayscale} />
    </AbsoluteFill>
  );
}

function Subtitles({ subtitles, theme }: { subtitles: DocumentaryProps["subtitles"]; theme: DocumentaryProps["theme"] }) {
  const frame = useCurrentFrame();
  const cur = subtitles.find((s) => frame >= s.startFrame && frame < s.endFrame);
  if (!cur) return null;
  if (theme === "cinematic") return <CineSubtitles text={cur.text} />;
  if (theme === "poster") return <PosterSubtitles text={cur.text} />;
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
    <AbsoluteFill style={{ background: props.theme === "cinematic" ? "#0e0c09" : props.theme === "poster" ? "#1d1b1a" : COLORS.paper }}>
      {props.scenes.map((scene, i) => (
        <Sequence
          key={scene.key}
          from={scene.startFrame}
          // overlap the next scene by the fade length so it can fade in over this one
          durationInFrames={scene.durationFrames + (i < last ? props.fadeFrames : 0)}
          layout="none"
        >
          <SceneView scene={scene} fade={props.fadeFrames} first={i === 0} grayscale={props.grayscale} theme={props.theme} />
        </Sequence>
      ))}
      {props.burnSubtitles && <Subtitles subtitles={props.subtitles} theme={props.theme} />}
    </AbsoluteFill>
  );
};
