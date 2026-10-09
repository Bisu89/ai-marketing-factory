import { Composition } from "remotion";
import type { CalculateMetadataFunction } from "remotion";
import { Documentary } from "./Documentary";
import { documentarySchema } from "./schema";
import type { DocumentaryProps } from "./schema";
import { Smoke, smokeSchema } from "./Smoke";

// 1920x1080 @ 30fps is the documentary's output format. Size/length really come from the
// manifest (calculateMetadata), so a preview at another scale is just a different manifest.
export const VIDEO = { width: 1920, height: 1080, fps: 30 } as const;

const EMPTY: DocumentaryProps = {
  fps: VIDEO.fps,
  width: VIDEO.width,
  height: VIDEO.height,
  durationInFrames: VIDEO.fps * 2,
  fadeFrames: 6,
  grayscale: true,
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
  </>
);
