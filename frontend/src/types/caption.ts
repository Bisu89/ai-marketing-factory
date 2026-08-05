export type CaptionJobStatus = "completed" | "failed";

export interface CaptionVersion {
  id: number;
  version_index: number;
  facebook_caption: string;
  instagram_caption: string;
  youtube_description: string;
  pinned_comment: string;
  cta: string;
  is_selected: boolean;
}

export interface CaptionJob {
  id: number;
  video_id: number;
  status: CaptionJobStatus;
  error_message: string | null;
  created_at: string;
  versions: CaptionVersion[];
}
