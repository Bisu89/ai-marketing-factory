import { Composition } from "remotion";
import type { CalculateMetadataFunction } from "remotion";
import { Documentary } from "./Documentary";
import { documentarySchema } from "./schema";
import type { DocumentaryProps } from "./schema";
import { Smoke, smokeSchema } from "./Smoke";
import { Video as PkScene7, DURATION as PkScene7_DURATION } from "./pk-ep01/Scene7";
import { Video as PkOpen, DURATION as PkOpen_DURATION } from "./pk-ep01/Open";

// 1920x1080 @ 30fps is the documentary's output format. Size/length really come from the
// manifest (calculateMetadata), so a preview at another scale is just a different manifest.
export const VIDEO = { width: 1920, height: 1080, fps: 30 } as const;

const EMPTY: DocumentaryProps = {
  fps: VIDEO.fps,
  width: VIDEO.width,
  height: VIDEO.height,
  durationInFrames: VIDEO.fps * 2,
  theme: "collage",
  fadeFrames: 6,
  grayscale: true,
  language: "vi",
  burnSubtitles: false,
  scenes: [],
  subtitles: [],
};

const calculateMetadata: CalculateMetadataFunction<DocumentaryProps> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: props.fps,
  width: props.width,
  height: props.height,
});

export const Root = () => (
  <>
    <Composition
      id="Documentary"
      component={Documentary}
      schema={documentarySchema}
      defaultProps={EMPTY}
      durationInFrames={EMPTY.durationInFrames}
      {...VIDEO}
      calculateMetadata={calculateMetadata}
    />
    <Composition
      id="Smoke"
      component={Smoke}
      schema={smokeSchema}
      defaultProps={{ headline: "Vox Documentary Factory" }}
      durationInFrames={VIDEO.fps * 2}
      {...VIDEO}
    />
    <Composition id="PkScene7" component={PkScene7} durationInFrames={PkScene7_DURATION} {...VIDEO} />
    <Composition
      id="PkOpen"
      component={PkOpen}
      durationInFrames={PkOpen_DURATION}
      {...VIDEO}
      defaultProps={{ music: 0.14, sfx: 1, voice: 1, captions: true }}
    />
  </>
);
