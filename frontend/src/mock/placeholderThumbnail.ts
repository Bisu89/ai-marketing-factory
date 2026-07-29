const PALETTE = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#0ea5e9"];

export function placeholderThumbnail(seed: number): string {
  const color = PALETTE[seed % PALETTE.length];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">
    <rect width="320" height="180" fill="${color}" />
    <polygon points="135,70 135,110 175,90" fill="rgba(255,255,255,0.85)" />
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
