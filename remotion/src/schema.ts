import { z } from "zod";

// The render manifest the backend writes (backend/app/modules/documentary/render_plan.py).
// All times are FRAMES, derived from the real narration timeline, never typed by hand.

export const PRESET_NAMES = [
  "NewspaperStack",
  "ArchivalPortrait",
  "MapZoom",
  "TimelineBuild",
  "BigNumber",
  "EvidenceBoard",
  "PhotoKenBurns",
  "HeadlineImpact",
  "SplitComparison",
] as const;

export const textSchema = z.object({
  text: z.string().min(1),
  role: z.enum(["headline", "label", "date", "number", "caption"]),
  // Frame (relative to the scene start) at which this text should appear, anchored
  // to the moment the matching word is spoken when timestamps allow.
  cueFrame: z.number().int().min(0),
});

export const sceneSchema = z.object({
  key: z.string(),
  preset: z.enum(PRESET_NAMES),
  startFrame: z.number().int().min(0),
  durationFrames: z.number().int().min(1),
  imageSrc: z.string().nullable(),
  texts: z.array(textSchema),
  claimStatus: z.enum(["verified", "disputed", "unverified"]).nullable(),
});

export const subtitleSchema = z.object({
  startFrame: z.number().int().min(0),
  endFrame: z.number().int().min(1),
  text: z.string(),
});

export const documentarySchema = z.object({
  fps: z.number().int().positive(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  durationInFrames: z.number().int().positive(),
  fadeFrames: z.number().int().min(0),
  grayscale: z.boolean(),
  burnSubtitles: z.boolean(),
  scenes: z.array(sceneSchema),
  subtitles: z.array(subtitleSchema),
});

export type Scene = z.infer<typeof sceneSchema>;
export type SceneText = z.infer<typeof textSchema>;
export type DocumentaryProps = z.infer<typeof documentarySchema>;
