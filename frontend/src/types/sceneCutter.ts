export type SceneCutStatus = "queued" | "analyzing" | "splitting" | "completed" | "failed";

export interface SceneOut {
  scene_number: number;
  start_timecode: string;
  end_timecode: string;
  file_path: string;
  media_url: string | null;
}

export interface SceneCutJob {
  id: number;
  video_id: number | null;
  source_path: string | null;
  threshold: number;
  min_scene_len_sec: number;
  trim_sec: number;
  requested_output_dir: string | null;
  status: SceneCutStatus;
  scene_count: number | null;
  output_dir: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  scenes: SceneOut[];
}

export interface CreateSceneJobInput {
  video_id?: number;
  source_path?: string;
  threshold: number;
  min_scene_len_sec: number;
  trim_sec: number;
  output_dir?: string;
}

// docs/features/107-scene-cutter-false-split-fix.md's Preview follow-up --
// detection only, no job/files created, so trying several threshold values
// is fast instead of a full cut-and-wait cycle each time.
export interface ScenePreviewItem {
  start_timecode: string;
  end_timecode: string;
  duration_sec: number;
}

export interface ScenePreview {
  scene_count: number;
  scenes: ScenePreviewItem[];
}
