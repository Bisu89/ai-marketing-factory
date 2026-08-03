export type StoryStyle =
  | "emotional"
  | "humorous"
  | "inspirational"
  | "dramatic"
  | "educational"
  | "sales";

export const STORY_STYLE_LABELS: Record<StoryStyle, string> = {
  emotional: "Cảm động",
  humorous: "Hài hước",
  inspirational: "Truyền cảm hứng",
  dramatic: "Kịch tính",
  educational: "Giáo dục",
  sales: "Bán hàng",
};

export type StoryJobStatus = "completed" | "failed";

export interface StoryVersion {
  id: number;
  version_index: number;
  title: string;
  script_text: string;
  is_selected: boolean;
}

export interface StoryJob {
  id: number;
  video_id: number;
  style: StoryStyle;
  status: StoryJobStatus;
  error_message: string | null;
  created_at: string;
  versions: StoryVersion[];
}

export interface StoryGenerateInput {
  video_id: number;
  style: StoryStyle;
}
