export type HookJobStatus = "completed" | "failed";

export interface Hook {
  id: number;
  hook_index: number;
  text: string;
  is_favorite: boolean;
}

export interface HookJob {
  id: number;
  video_id: number;
  status: HookJobStatus;
  error_message: string | null;
  created_at: string;
  hooks: Hook[];
}
