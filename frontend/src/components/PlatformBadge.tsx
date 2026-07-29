import type { Platform } from "../types/video";
import { formatPlatformLabel } from "../utils/format";
import "./PlatformBadge.css";

export function PlatformBadge({ platform }: { platform: Platform }) {
  return <span className={`platform-badge platform-badge--${platform}`}>{formatPlatformLabel(platform)}</span>;
}
