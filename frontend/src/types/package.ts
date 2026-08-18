// Mirrors app/api/v1/endpoints/package_generate.py's PackageOut/
// PackageOverridesIn -- see docs/features/53-thumbnail-metadata-package.md.

export interface ReadyToPostPackage {
  title: string | null;
  description: string | null;
  hashtags: string[];
  language: string | null;
  category: string | null;
  platform_profile: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  aspect_ratio: string | null;
  thumbnail_path: string | null;
  video_path: string | null;
  thumbnail_media_url: string | null;
  video_media_url: string | null;
  manual_title: string | null;
  manual_description: string | null;
  manual_hashtags: string[] | null;
  is_complete: boolean;
}

export interface PackageOverrides {
  title?: string;
  description?: string;
  hashtags?: string[];
  clear_title?: boolean;
  clear_description?: boolean;
  clear_hashtags?: boolean;
}
