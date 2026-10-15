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
  // A schematic troop-movement/sequence-of-places diagram (unit blocks + drawn-on arrows between
  // named points) -- not real geography, same spirit as MapZoom's own decorative fallback. See
  // docs/documentary/PORTING_NOTES.md.
  "TacticalMap",
] as const;

// Optional continuous particle overlay drawn over whatever preset is showing (snow/rain/wind/rising
// embers). Manually set per scene, never guessed from narration. See PORTING_NOTES.md part C.
export const AMBIENT_KINDS = ["rain", "snow", "wind", "embers"] as const;

export const textSchema = z.object({
  text: z.string().min(1),
  // optional one-line context shown under a date (what happened then), cut from the narration
  sub: z.string().nullable(),
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
  // width / height of the image (null when unknown) -- lets a theme lay out portrait images differently.
  imageAspect: z.number().positive().nullable(),
  texts: z.array(textSchema),
  claimStatus: z.enum(["verified", "disputed", "unverified"]).nullable(),
  ambient: z.enum(AMBIENT_KINDS).nullable().optional(),
});

export const subtitleSchema = z.object({
  startFrame: z.number().int().min(0),
  endFrame: z.number().int().min(1),
  text: z.string(),
});

export const THEMES = ["collage", "cinematic", "poster"] as const;

export const documentarySchema = z.object({
  theme: z.enum(THEMES),
  fps: z.number().int().positive(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  durationInFrames: z.number().int().positive(),
  fadeFrames: z.number().int().min(0),
  grayscale: z.boolean(),
  language: z.string().default("vi"),
  burnSubtitles: z.boolean(),
  scenes: z.array(sceneSchema),
  subtitles: z.array(subtitleSchema),
});

export type Scene = z.infer<typeof sceneSchema>;
export type SceneText = z.infer<typeof textSchema>;
export type DocumentaryProps = z.infer<typeof documentarySchema>;
