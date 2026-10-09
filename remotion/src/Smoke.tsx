import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";

export const smokeSchema = z.object({ headline: z.string().min(1) });

export const Smoke = ({ headline }: z.infer<typeof smokeSchema>) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#f1e9d8", alignItems: "center", justifyContent: "center" }}>
      <h1 style={{ opacity, fontSize: 96, fontFamily: "Georgia, serif", color: "#1a1a1a" }}>{headline}</h1>
    </AbsoluteFill>
  );
};
