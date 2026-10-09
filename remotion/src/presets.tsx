import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { ARCHIVAL_FILTER, COLORS, FONTS, MOTION } from "./theme";
import { Halftone, Highlight, PaperBackground, PaperCard, RedCircle, Tape, ease, headlineStyle, rng, tornPolygon, useEnter } from "./collage";
import type { Scene, SceneText } from "./schema";

export interface PresetProps {
  scene: Scene;
  grayscale: boolean;
}

// ---- small helpers ---------------------------------------------------------------
const byRole = (s: Scene, ...roles: SceneText["role"][]) => s.texts.filter((t) => roles.includes(t.role));
const firstText = (s: Scene, ...roles: SceneText["role"][]) => byRole(s, ...roles)[0];

/** Shrink long text so it stays inside its box (Vietnamese runs long). */
function fit(text: string, base: number, maxChars: number): number {
  return Math.round(base * Math.min(1, maxChars / Math.max(text.length, 1)));
}

function Photo({ scene, grayscale, style }: { scene: Scene; grayscale: boolean; style?: CSSProperties }) {
  if (!scene.imageSrc) return null;
  return (
    <Img
      src={staticFile(scene.imageSrc)}
      style={{ width: "100%", height: "100%", objectFit: "cover", filter: grayscale ? ARCHIVAL_FILTER : undefined, ...style }}
    />
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.paperDark, display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
      <Halftone opacity={0.2} />
      <span style={{ fontFamily: FONTS.sans, color: COLORS.inkSoft, fontSize: 30 }}>{label}</span>
    </div>
  );
}

function Appear({ at, children, style }: { at: number; children: ReactNode; style?: CSSProperties }) {
  const p = useEnter(at);
  return <div style={{ opacity: p, transform: `translateY(${(1 - p) * 26}px)`, ...style }}>{children}</div>;
}

function Label({ children, at = 0, style }: { children: string; at?: number; style?: CSSProperties }) {
  return (
    <Appear at={at} style={{ position: "absolute", ...style }}>
      <div style={{ background: COLORS.paperLight, padding: "10px 24px", fontFamily: FONTS.sans, fontWeight: 700, fontSize: fit(children, 42, 34), color: COLORS.ink, boxShadow: `0 6px 10px ${COLORS.shadow}`, clipPath: tornPolygon(children + "label", 0.8, 12) }}>
        {children}
      </div>
    </Appear>
  );
}

// ---- 1. PhotoKenBurns --------------------------------------------------------------
export function PhotoKenBurns({ scene, grayscale }: PresetProps) {
  const frame = useCurrentFrame();
  const enter = useEnter(0, 16);
  const t = frame / Math.max(scene.durationFrames, 1);
  const zoom = 1 + MOTION.kenBurnsZoom * t;
  const caption = firstText(scene, "caption", "label", "headline");
  const dir = scene.key.charCodeAt(scene.key.length - 1) % 2 === 0 ? 1 : -1;
  return (
    <AbsoluteFill>
      <PaperBackground />
      <PaperCard seed={scene.key} rotate={-1.1 * dir} style={{ left: 190, top: 90, width: 1540, height: 840, transform: `rotate(${-1.1 * dir}deg) scale(${0.96 + 0.04 * enter})`, opacity: enter }} jitter={1.1}>
        <div style={{ position: "absolute", inset: 18, overflow: "hidden", background: COLORS.paperDark }}>
          {scene.imageSrc ? <Photo scene={scene} grayscale={grayscale} style={{ transform: `scale(${zoom}) translateX(${dir * t * -16}px)` }} /> : <Placeholder label="Chưa có ảnh" />}
        </div>
      </PaperCard>
      <Tape rotate={-8} style={{ left: 160, top: 70 }} />
      <Tape rotate={7} style={{ right: 150, top: 80 }} />
      {caption && <Label at={caption.cueFrame} style={{ left: 250, bottom: 190 }}>{caption.text}</Label>}
    </AbsoluteFill>
  );
}

// ---- 2. ArchivalPortrait ---------------------------------------------------------------
export function ArchivalPortrait({ scene, grayscale }: PresetProps) {
  const enter = useEnter(0, 16);
  const head = firstText(scene, "headline", "caption");
  const date = firstText(scene, "date");
  const label = firstText(scene, "label");
  return (
    <AbsoluteFill>
      <PaperBackground />
      <PaperCard seed={scene.key} rotate={-2.2} style={{ left: 220, top: 110, width: 640, height: 830, opacity: enter, transform: `rotate(-2.2deg) translateX(${(1 - enter) * -80}px)` }} jitter={1.2}>
        <div style={{ position: "absolute", inset: 22, overflow: "hidden", background: COLORS.paperDark }}>
          {scene.imageSrc ? <Photo scene={scene} grayscale={grayscale} /> : <Placeholder label="Chưa có ảnh" />}
        </div>
      </PaperCard>
      <Tape rotate={-14} style={{ left: 190, top: 90 }} />
      <RedCircle x={330} y={210} w={330} h={380} delay={34} />
      {head && (
        <div style={{ position: "absolute", left: 960, top: 250, width: 820 }}>
          <Appear at={head.cueFrame + 6}>
            <div style={{ ...headlineStyle, fontSize: fit(head.text, 130, 14) }}>
              <Highlight delay={head.cueFrame + 14}>{head.text}</Highlight>
            </div>
          </Appear>
        </div>
      )}
      {date && <Label at={date.cueFrame} style={{ left: 970, top: 640 }}>{date.text}</Label>}
      {label && <Label at={label.cueFrame} style={{ left: 970, top: 730 }}>{label.text}</Label>}
    </AbsoluteFill>
  );
}

// ---- 3. NewspaperStack --------------------------------------------------------------------
export function NewspaperStack({ scene, grayscale }: PresetProps) {
  const items = scene.texts.slice(0, 4);
  const r = rng(scene.key);
  return (
    <AbsoluteFill>
      <PaperBackground tint={COLORS.paperDark} />
      {items.map((t, i) => {
        const x = 330 + i * 150 + (r() - 0.5) * 40;
        const y = 150 + i * 130;
        const rot = (r() - 0.5) * 7;
        const isTop = i === items.length - 1;
        return (
          <Appear key={i} at={Math.max(t.cueFrame, i * MOTION.stagger)} style={{ position: "absolute", left: 0, top: 0 }}>
            <PaperCard seed={`${scene.key}-${i}`} rotate={rot} color="#f3ead4" style={{ left: x, top: y, width: 900, height: 360 }} jitter={1.0}>
              <Halftone opacity={0.07} size={8} />
              <div style={{ position: "absolute", left: 40, top: 26, right: 40 }}>
                <div style={{ fontFamily: FONTS.serif, fontWeight: 700, fontSize: fit(t.text, 56, 30), color: COLORS.ink, lineHeight: 1.08 }}>
                  {isTop ? <Highlight delay={t.cueFrame + 10}>{t.text}</Highlight> : t.text}
                </div>
                {/* Grey bars stand in for body text: no invented copy. */}
                {[0, 1, 2, 3].map((n) => (
                  <div key={n} style={{ height: 11, marginTop: 14, width: `${96 - n * 9 - r() * 8}%`, background: "rgba(40,36,28,0.22)" }} />
                ))}
              </div>
              {isTop && scene.imageSrc && (
                <div style={{ position: "absolute", right: 36, bottom: 26, width: 270, height: 150, overflow: "hidden" }}>
                  <Photo scene={scene} grayscale={grayscale} />
                </div>
              )}
            </PaperCard>
          </Appear>
        );
      })}
      {items.length === 0 && scene.imageSrc && (
        <PaperCard seed={scene.key} style={{ left: 500, top: 140, width: 920, height: 800 }}>
          <Photo scene={scene} grayscale={grayscale} />
        </PaperCard>
      )}
    </AbsoluteFill>
  );
}

// ---- 4. MapZoom ----------------------------------------------------------------------------------
function Contours({ seed }: { seed: string }) {
  const r = rng(seed);
  const rings = Array.from({ length: 9 }, (_, i) => {
    const rx = 120 + i * 105;
    const ry = 70 + i * 62;
    const pts = Array.from({ length: 36 }, (_, k) => {
      const a = (k / 36) * Math.PI * 2;
      const w = 1 + (r() - 0.5) * 0.14;
      return `${960 + Math.cos(a) * rx * w},${540 + Math.sin(a) * ry * w}`;
    });
    return `M${pts.join("L")}Z`;
  });
  return (
    <svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
      {rings.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={COLORS.blue} strokeOpacity={0.28} strokeWidth={2.4} />
      ))}
    </svg>
  );
}

export function MapZoom({ scene, grayscale }: PresetProps) {
  const frame = useCurrentFrame();
  const t = Math.min(1, frame / Math.max(scene.durationFrames * 0.8, 1));
  const zoom = interpolate(t, [0, 1], [1, scene.imageSrc ? 1.9 : 1.35], { easing: ease });
  const pin = useEnter(24, 16);
  const place = firstText(scene, "label", "headline", "caption");
  return (
    <AbsoluteFill>
      <PaperBackground />
      <div style={{ position: "absolute", inset: 0, transform: `scale(${zoom})`, transformOrigin: "62% 46%" }}>
        {scene.imageSrc ? (
          <PaperCard seed={scene.key} style={{ left: 160, top: 90, width: 1600, height: 900 }} jitter={1.0}>
            <div style={{ position: "absolute", inset: 16, overflow: "hidden" }}>
              <Photo scene={scene} grayscale={grayscale} />
            </div>
          </PaperCard>
        ) : (
          <Contours seed={scene.key} />
        )}
        <div style={{ position: "absolute", left: 1190 - 20, top: 500 - 70 + (1 - pin) * -60, opacity: pin }}>
          <div style={{ width: 40, height: 40, borderRadius: 40, background: COLORS.red, border: `5px solid ${COLORS.paperLight}`, boxShadow: `0 5px 8px ${COLORS.shadow}` }} />
          <div style={{ width: 6, height: 40, background: COLORS.red, margin: "-4px auto 0" }} />
        </div>
      </div>
      {place && <Label at={place.cueFrame + 8} style={{ left: 120, bottom: 200 }}>{place.text}</Label>}
    </AbsoluteFill>
  );
}

function Marker({ x, y, at }: { x: number; y: number; at: number }) {
  const grow = useEnter(at, 10);
  return <div style={{ position: "absolute", left: x - 16, top: y - 16, width: 32, height: 32, borderRadius: 32, background: COLORS.red, transform: `scale(${grow})`, border: `5px solid ${COLORS.paperLight}` }} />;
}

// ---- 5. TimelineBuild --------------------------------------------------------------------------------
export function TimelineBuild({ scene }: PresetProps) {
  const frame = useCurrentFrame();
  const dates = byRole(scene, "date", "number").slice(0, 5);
  const notes = scene.texts.filter((t) => !dates.includes(t)).slice(0, 3);
  const draw = interpolate(frame, [0, 28], [0, 1], { extrapolateRight: "clamp", easing: ease });
  const lineY = 540;
  return (
    <AbsoluteFill>
      <PaperBackground />
      <div style={{ position: "absolute", left: 160, top: lineY - 4, width: 1600 * draw, height: 8, background: COLORS.ink }} />
      {dates.map((d, i) => {
        const x = dates.length === 1 ? 960 : 260 + (i * 1400) / (dates.length - 1);
        const at = Math.max(d.cueFrame, 18 + i * MOTION.stagger);
        const up = i % 2 === 0;
        return (
          <Appear key={i} at={at} style={{ position: "absolute", left: x - 190, top: up ? lineY - 250 : lineY + 40, width: 380, textAlign: "center" }}>
            <div style={{ ...headlineStyle, fontSize: fit(d.text, 112, 8) }}>
              <Highlight delay={at + 6}>{d.text}</Highlight>
            </div>
          </Appear>
        );
      })}
      {dates.map((d, i) => (
        <Marker key={`m${i}`} x={dates.length === 1 ? 960 : 260 + (i * 1400) / (dates.length - 1)} y={lineY} at={Math.max(d.cueFrame, 18 + i * MOTION.stagger)} />
      ))}
      {notes.map((n, i) => (
        <Label key={i} at={Math.max(n.cueFrame, 30)} style={{ left: 220, bottom: 190 + i * 76 }}>{n.text}</Label>
      ))}
    </AbsoluteFill>
  );
}

// ---- 6. BigNumber ----------------------------------------------------------------------------------------
export function BigNumber({ scene }: PresetProps) {
  const frame = useCurrentFrame();
  const num = firstText(scene, "number", "date", "headline");
  const unit = firstText(scene, "label", "caption");
  const enter = useEnter(0, 14);
  const plain = num && /^\d{1,12}$/.test(num.text);
  const count = interpolate(frame, [4, 36], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const shown = num ? (plain ? String(Math.round(Number(num.text) * count)) : num.text) : "";
  return (
    <AbsoluteFill>
      <PaperBackground tint={COLORS.paperDark} />
      <Halftone opacity={0.1} size={18} />
      {num && (
        <div style={{ position: "absolute", left: 0, right: 0, top: 220, textAlign: "center", transform: `scale(${0.9 + 0.1 * enter})`, opacity: enter }}>
          <div style={{ ...headlineStyle, fontSize: fit(num.text, 360, 7) }}>
            <Highlight delay={10}>{shown}</Highlight>
          </div>
        </div>
      )}
      {unit && (
        <Label at={Math.max(unit.cueFrame, 16)} style={{ left: 0, right: 0, bottom: 200, display: "flex", justifyContent: "center" }}>
          {unit.text}
        </Label>
      )}
    </AbsoluteFill>
  );
}

// ---- 7. EvidenceBoard -----------------------------------------------------------------------------------------
export function EvidenceBoard({ scene }: PresetProps) {
  const cards = scene.texts.slice(0, 4);
  const stamp = useEnter(40, 10);
  const LAYOUTS: Record<number, { x: number; y: number }[]> = {
    0: [],
    1: [{ x: 610, y: 380 }],
    2: [{ x: 170, y: 380 }, { x: 1050, y: 340 }],
    3: [{ x: 200, y: 150 }, { x: 1000, y: 180 }, { x: 600, y: 580 }],
    4: [{ x: 200, y: 130 }, { x: 1000, y: 160 }, { x: 260, y: 560 }, { x: 1040, y: 590 }],
  };
  const pos = LAYOUTS[cards.length] ?? LAYOUTS[4];
  const r = rng(scene.key);
  const rots = cards.map(() => (r() - 0.5) * 6);
  const pins = cards.map((_, i) => ({ x: pos[i].x + 350, y: pos[i].y + 24 }));
  const drawn = useEnter(26, 24);
  return (
    <AbsoluteFill>
      <PaperBackground tint={"#d8c7a2"} />
      <Halftone opacity={0.1} size={16} />
      <svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }}>
        {pins.slice(1).map((p, i) => (
          <line key={i} x1={pins[i].x} y1={pins[i].y} x2={pins[i].x + (p.x - pins[i].x) * drawn} y2={pins[i].y + (p.y - pins[i].y) * drawn} stroke={COLORS.red} strokeWidth={4} />
        ))}
      </svg>
      {cards.map((t, i) => (
        <Appear key={i} at={Math.max(t.cueFrame, i * MOTION.stagger)} style={{ position: "absolute", left: 0, top: 0 }}>
          <PaperCard seed={`${scene.key}-${i}`} rotate={rots[i]} style={{ left: pos[i].x, top: pos[i].y, width: 700, height: 330 }} jitter={0.8}>
            <div style={{ padding: "52px 40px", fontFamily: FONTS.serif, fontWeight: 700, fontSize: fit(t.text, 56, 40), color: COLORS.ink, lineHeight: 1.18 }}>{t.text}</div>
          </PaperCard>
          <div style={{ position: "absolute", left: pins[i].x - 14, top: pins[i].y - 14, width: 28, height: 28, borderRadius: 28, background: COLORS.red, boxShadow: `0 4px 6px ${COLORS.shadow}` }} />
        </Appear>
      ))}
      {scene.claimStatus && scene.claimStatus !== "unverified" && (
        <div style={{ position: "absolute", right: 120, bottom: 190, transform: `rotate(-6deg) scale(${1.4 - 0.4 * stamp})`, opacity: stamp, border: `8px solid ${scene.claimStatus === "disputed" ? COLORS.red : COLORS.blue}`, color: scene.claimStatus === "disputed" ? COLORS.red : COLORS.blue, fontFamily: FONTS.display, fontSize: 60, padding: "6px 26px", letterSpacing: "0.04em" }}>
          {scene.claimStatus === "disputed" ? "CÒN TRANH CÃI" : "ĐÃ XÁC MINH"}
        </div>
      )}
    </AbsoluteFill>
  );
}

// ---- 8. HeadlineImpact ----------------------------------------------------------------------------------------------
export function HeadlineImpact({ scene }: PresetProps) {
  const head = firstText(scene, "headline", "caption", "label", "number", "date");
  const sub = scene.texts.find((t) => t !== head);
  const words = head ? head.text.split(/\s+/).slice(0, 9) : [];
  const chips = [COLORS.paperLight, COLORS.yellow, COLORS.ink, COLORS.paperLight, COLORS.red];
  const r = rng(scene.key);
  const size = fit(head?.text ?? "", 150, 18);
  return (
    <AbsoluteFill>
      <PaperBackground tint={COLORS.paperDark} />
      <Halftone opacity={0.1} size={16} />
      <div style={{ position: "absolute", left: 140, right: 140, top: 260, display: "flex", flexWrap: "wrap", gap: 18, justifyContent: "center" }}>
        {words.map((w, i) => (
          <HeadlineChip key={i} index={i} bg={chips[i % chips.length]} rot={(r() - 0.5) * 6} size={size}>
            {w}
          </HeadlineChip>
        ))}
      </div>
      {sub && <Label at={Math.max(sub.cueFrame, 30)} style={{ left: 0, right: 0, bottom: 200, display: "flex", justifyContent: "center" }}>{sub.text}</Label>}
    </AbsoluteFill>
  );
}

function HeadlineChip({ children, index, bg, rot, size }: { children: string; index: number; bg: string; rot: number; size: number }) {
  const p = useEnter(index * 5, 9);
  const dark = bg === COLORS.ink || bg === COLORS.red;
  return (
    <div style={{ background: bg, padding: "6px 26px", transform: `rotate(${rot}deg) scale(${1.3 - 0.3 * p})`, opacity: p, boxShadow: `0 8px 12px ${COLORS.shadow}`, clipPath: tornPolygon(children + index, 0.7, 10) }}>
      <span style={{ ...headlineStyle, fontSize: size, color: dark ? COLORS.paperLight : COLORS.ink }}>{children}</span>
    </div>
  );
}

// ---- 9. SplitComparison ------------------------------------------------------------------------------------------------
export function SplitComparison({ scene, grayscale }: PresetProps) {
  const enter = useEnter(0, 16);
  const [a, b] = [scene.texts[0], scene.texts[1]];
  return (
    <AbsoluteFill>
      <PaperBackground />
      <PaperCard seed={`${scene.key}-l`} rotate={-1.5} style={{ left: 140, top: 150, width: 820, height: 700, opacity: enter, transform: `rotate(-1.5deg) translateX(${(1 - enter) * -90}px)` }}>
        <div style={{ position: "absolute", inset: 18, overflow: "hidden", background: COLORS.paperDark }}>
          {scene.imageSrc ? <Photo scene={scene} grayscale={grayscale} /> : <Placeholder label="" />}
        </div>
      </PaperCard>
      <PaperCard seed={`${scene.key}-r`} rotate={1.4} color={COLORS.paperDark} style={{ left: 980, top: 150, width: 800, height: 700, opacity: enter, transform: `rotate(1.4deg) translateX(${(1 - enter) * 90}px)` }}>
        <Halftone opacity={0.12} />
        {b && (
          <Appear at={Math.max(b.cueFrame, 24)} style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: 60, textAlign: "center" }}>
            <div style={{ ...headlineStyle, fontSize: fit(b.text, 96, 16) }}>
              <Highlight delay={Math.max(b.cueFrame, 24) + 8}>{b.text}</Highlight>
            </div>
          </Appear>
        )}
      </PaperCard>
      {a && <Label at={Math.max(a.cueFrame, 12)} style={{ left: 190, top: 790 }}>{a.text}</Label>}
    </AbsoluteFill>
  );
}

export const PRESET_COMPONENTS = {
  PhotoKenBurns,
  ArchivalPortrait,
  NewspaperStack,
  MapZoom,
  TimelineBuild,
  BigNumber,
  EvidenceBoard,
  HeadlineImpact,
  SplitComparison,
} as const;

