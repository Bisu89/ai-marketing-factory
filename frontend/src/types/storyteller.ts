export type StorytellerStatus = "pending" | "narrating" | "compositing" | "completed" | "failed";
export type StorytellerAssetKind = "background" | "avatar";
export type StorytellerLayout = "single" | "triptych";

export interface StorytellerEpisode {
  id: number;
  title: string;
  word_count: number;
  voice: string;
  narration_rate: string;
  burn_captions: boolean;
  layout: StorytellerLayout;
  background_asset_id: number | null;
  avatar_asset_id: number | null;
  left_asset_id: number | null;
  middle_asset_id: number | null;
  right_asset_id: number | null;
  disclaimer_text: string | null;
  story_title: string | null;
  story_author: string | null;
  story_character: string | null;
  status: StorytellerStatus;
  progress_stage: string | null;
  error_message: string | null;
  output_path: string | null;
  duration_sec: number | null;
  created_at: string;
  updated_at: string;
}

export type StorytellerMediaType = "image" | "video";

export interface StorytellerAsset {
  id: number;
  kind: StorytellerAssetKind;
  media_type: StorytellerMediaType;
  name: string;
  path: string;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  key_color: string | null;
  created_at: string;
}

export interface CreateEpisodeInput {
  title: string;
  script_text: string;
  voice?: string;
  narration_rate?: string;
  burn_captions?: boolean;
  layout?: StorytellerLayout;
  background_asset_id?: number | null;
  avatar_asset_id?: number | null;
  left_asset_id?: number | null;
  middle_asset_id?: number | null;
  right_asset_id?: number | null;
  disclaimer_text?: string | null;
  story_title?: string | null;
  story_author?: string | null;
  story_character?: string | null;
}
