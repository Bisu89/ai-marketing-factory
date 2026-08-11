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

export type StoryLanguage = "english" | "spanish" | "vietnamese";

export const STORY_LANGUAGE_LABELS: Record<StoryLanguage, string> = {
  english: "Tiếng Anh",
  spanish: "Tiếng Tây Ban Nha",
  vietnamese: "Tiếng Việt",
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
  language: StoryLanguage;
  status: StoryJobStatus;
  error_message: string | null;
  created_at: string;
  versions: StoryVersion[];
}

export interface StoryGenerateInput {
  video_id: number;
  style: StoryStyle;
  language: StoryLanguage;
}
