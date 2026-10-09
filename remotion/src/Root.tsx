import { Composition } from "remotion";
import { Smoke, smokeSchema } from "./Smoke";

// 1920x1080 @ 30fps is the documentary's fixed output format. The real
// presets (NewspaperStack, MapZoom, ...) are added in Phase 5; "Smoke" only
// proves the toolchain renders.
export const VIDEO = { width: 1920, height: 1080, fps: 30 } as const;

export const Root = () => (
  <Composition
    id="Smoke"
    component={Smoke}
    schema={smokeSchema}
    defaultProps={{ headline: "Vox Documentary Factory" }}
    durationInFrames={VIDEO.fps * 2}
    {...VIDEO}
  />
);
