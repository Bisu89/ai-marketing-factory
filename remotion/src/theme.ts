// One consistent look for the whole documentary: warm paper, archival muted
// photos, bold editorial type, restrained yellow highlight, optional red
// annotation. System fonts only (Georgia / Arial / Impact ship with Windows and
// cover Vietnamese diacritics -- except Georgia, hence Times New Roman for serif) so rendering
// needs no network and no licence.

export const COLORS = {
  paper: "#efe6d2",
  paperDark: "#e0d3b8",
  paperLight: "#f7f1e3",
  ink: "#1b1a17",
  inkSoft: "#4a463e",
  yellow: "#f2c230",
  red: "#c8352b",
  blue: "#35566f",
  shadow: "rgba(30, 22, 10, 0.38)",
} as const;

export const FONTS = {
  // Times New Roman has the full Vietnamese glyph set; Georgia lacks stacked marks (ế, ằ) and
  // falls back to detached accents.
  serif: '"Times New Roman", "Cambria", "Georgia", serif',
  sans: '"Arial", "Segoe UI", sans-serif',
  display: '"Impact", "Arial Black", "Arial", sans-serif',
} as const;

// Shared motion constants so every preset eases the same way.
export const MOTION = {
  enterFrames: 14,
  stagger: 9,
  kenBurnsZoom: 0.07,
} as const;

export const ARCHIVAL_FILTER = "grayscale(0.85) sepia(0.28) contrast(1.06) brightness(0.98)";
