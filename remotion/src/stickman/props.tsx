import React from "react";
import { COL, FONT } from "./fx";

// SVG props centred on (0,0): position them with <At>
export const At: React.FC<{ x: number; y: number; s?: number; r?: number; o?: number; children: React.ReactNode }> = ({ x, y, s = 1, r = 0, o = 1, children }) => (
  <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`} opacity={o}>
    {children}
  </g>
);

const K = { stroke: COL.ink, strokeWidth: 6, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

export const Barrel: React.FC<{ label?: string }> = ({ label = "OIL" }) => (
  <g>
    <rect x={-50} y={-70} width={100} height={140} rx={14} fill="#2b2b2b" {...K} />
    <rect x={-50} y={-38} width={100} height={10} fill="#555" />
    <rect x={-50} y={28} width={100} height={10} fill="#555" />
    <ellipse cx={0} cy={-70} rx={50} ry={10} fill="#3b3b3b" {...K} />
    <text x={0} y={12} textAnchor="middle" fontFamily={FONT.comic} fontSize={34} fill={COL.yellow}>
      {label}
    </text>
  </g>
);

export const Bill: React.FC<{ w?: number; sym?: string; color?: string }> = ({ w = 150, sym = "$", color = COL.dollar }) => (
  <g>
    <rect x={-w / 2} y={-w * 0.23} width={w} height={w * 0.46} rx={6} fill="#cfe8c8" stroke={color} strokeWidth={5} />
    <rect x={-w / 2 + 8} y={-w * 0.23 + 8} width={w - 16} height={w * 0.46 - 16} rx={3} fill="none" stroke={color} strokeWidth={2} />
    <circle cx={0} cy={0} r={w * 0.15} fill={color} />
    <text x={0} y={w * 0.075} textAnchor="middle" fontFamily={FONT.title} fontWeight={900} fontSize={w * 0.22} fill="#cfe8c8">
      {sym}
    </text>
  </g>
);

export const GoldBar: React.FC<{ label?: string }> = ({ label }) => (
  <g>
    <polygon points="-70,30 70,30 50,-25 -50,-25" fill={COL.gold} {...K} />
    <polygon points="-50,-25 50,-25 40,-34 -40,-34" fill="#ffe27a" {...K} strokeWidth={4} />
    <line x1={-35} y1={-12} x2={-10} y2={-12} stroke="#fff6c8" strokeWidth={6} strokeLinecap="round" />
    {label && (
      <text x={0} y={18} textAnchor="middle" fontFamily={FONT.title} fontWeight={900} fontSize={26} fill={COL.ink}>
        {label}
      </text>
    )}
  </g>
);

export const Coin: React.FC<{ sym: string; color?: string; r?: number }> = ({ sym, color = COL.gold, r = 60 }) => (
  <g>
    <circle r={r} fill={color} {...K} />
    <circle r={r * 0.78} fill="none" stroke="rgba(0,0,0,0.25)" strokeWidth={4} />
    <text y={r * 0.33} textAnchor="middle" fontFamily={FONT.title} fontWeight={900} fontSize={r * 0.95} fill={COL.ink}>
      {sym}
    </text>
  </g>
);

export const Shield: React.FC<{ crack?: number; color?: string }> = ({ crack = 0, color = COL.blue }) => (
  <g>
    <path d="M0,-90 L75,-62 Q75,40 0,95 Q-75,40 -75,-62 Z" fill={color} {...K} />
    <path d="M0,-66 L52,-46 Q52,28 0,68 Q-52,28 -52,-46 Z" fill="none" stroke="#fff" strokeWidth={6} opacity={0.6} />
    <text y={22} textAnchor="middle" fontFamily={FONT.title} fontWeight={900} fontSize={70} fill="#fff">
      ★
    </text>
    {crack > 0 && (
      <polyline
        points="-10,-90 6,-50 -14,-20 12,10 -6,40 8,95"
        fill="none"
        stroke={COL.ink}
        strokeWidth={7}
        strokeDasharray={260}
        strokeDashoffset={260 * (1 - crack)}
        strokeLinejoin="round"
      />
    )}
  </g>
);

export const Missile: React.FC = () => (
  <g>
    <path d="M-80,-14 L50,-14 Q90,0 50,14 L-80,14 Z" fill="#d9d9d9" {...K} />
    <polygon points="-80,-14 -110,-36 -96,0 -110,36 -80,14" fill={COL.red} {...K} />
    <circle cx={-118} cy={0} r={14} fill={COL.orange} opacity={0.9} />
    <circle cx={-140} cy={0} r={9} fill={COL.yellow} opacity={0.8} />
  </g>
);

export const Printer: React.FC<{ f: number }> = ({ f }) => (
  <g>
    <rect x={-110} y={-60} width={220} height={110} rx={16} fill="#e8e6df" {...K} />
    <rect x={-80} y={-95} width={160} height={40} rx={6} fill="#fff" {...K} />
    <rect x={-90} y={30} width={180} height={14} rx={7} fill={COL.ink} />
    <circle cx={80} cy={-25} r={10} fill={Math.floor(f / 6) % 2 ? COL.green : "#9ad59f"} />
    <text x={-30} y={0} textAnchor="middle" fontFamily={FONT.title} fontWeight={900} fontSize={34} fill={COL.ink}>
      FED
    </text>
  </g>
);

export const Bank: React.FC<{ label: string; color?: string; w?: number }> = ({ label, color = "#e8e6df", w = 220 }) => (
  <g>
    <polygon points={`${-w / 2 - 15},-70 0,-140 ${w / 2 + 15},-70`} fill={color} {...K} />
    <rect x={-w / 2} y={-70} width={w} height={20} fill={color} {...K} />
    {[-0.36, -0.12, 0.12, 0.36].map((k) => (
      <rect key={k} x={w * k - 11} y={-50} width={22} height={110} fill="#fff" {...K} strokeWidth={4} />
    ))}
    <rect x={-w / 2 - 15} y={60} width={w + 30} height={22} fill={color} {...K} />
    <text y={120} textAnchor="middle" fontFamily={FONT.title} fontWeight={800} fontSize={34} fill={COL.ink}>
      {label}
    </text>
  </g>
);

export const Box: React.FC<{ label?: string; color?: string }> = ({ label, color = "#d9a066" }) => (
  <g>
    <rect x={-48} y={-42} width={96} height={84} rx={4} fill={color} {...K} />
    <line x1={-48} y1={-14} x2={48} y2={-14} stroke={COL.ink} strokeWidth={4} />
    {label && (
      <text y={24} textAnchor="middle" fontSize={40}>
        {label}
      </text>
    )}
  </g>
);

export const Ship: React.FC<{ color?: string }> = ({ color = "#555" }) => (
  <g>
    <path d="M-160,0 L160,0 L130,50 L-140,50 Z" fill={color} {...K} />
    <rect x={60} y={-60} width={60} height={60} fill="#e8e6df" {...K} />
    <rect x={80} y={-90} width={16} height={30} fill={COL.ink} />
    <rect x={-120} y={-34} width={160} height={34} rx={4} fill={COL.red} {...K} strokeWidth={4} />
  </g>
);

export const Ice: React.FC<{ w: number; h: number }> = ({ w, h }) => (
  <g>
    <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={18} fill="rgba(160,215,245,0.6)" stroke="#4aa3d8" strokeWidth={6} />
    <polyline points={`${-w / 2 + 20},${-h / 2 + 30} ${-w / 2 + 60},${-h / 2 + 15}`} stroke="#fff" strokeWidth={8} strokeLinecap="round" />
    <polyline points={`${w / 2 - 50},${h / 2 - 20} ${w / 2 - 20},${h / 2 - 40}`} stroke="#fff" strokeWidth={6} strokeLinecap="round" />
  </g>
);

export const Chain: React.FC<{ x1: number; y1: number; x2: number; y2: number; t: number; color?: string }> = ({ x1, y1, x2, y2, t, color = COL.blue }) => {
  const n = 9;
  const ang = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
  const shown = Math.floor(n * t);
  return (
    <g>
      {Array.from({ length: shown }).map((_, i) => {
        const k = (i + 0.5) / n;
        return (
          <rect
            key={i}
            x={-22}
            y={-11}
            width={44}
            height={22}
            rx={11}
            fill="none"
            stroke={color}
            strokeWidth={7}
            transform={`translate(${x1 + (x2 - x1) * k} ${y1 + (y2 - y1) * k}) rotate(${ang + (i % 2) * 0})`}
          />
        );
      })}
    </g>
  );
};

// simple flag with label
export const Flag: React.FC<{ colors: string[]; label?: string; vertical?: boolean }> = ({ colors, label, vertical }) => (
  <g>
    <line x1={0} y1={0} x2={0} y2={-150} stroke={COL.ink} strokeWidth={7} strokeLinecap="round" />
    {colors.map((c, i) =>
      vertical ? (
        <rect key={i} x={(i * 90) / colors.length} y={-150} width={90 / colors.length} height={60} fill={c} />
      ) : (
        <rect key={i} x={0} y={-150 + (i * 60) / colors.length} width={90} height={60 / colors.length} fill={c} />
      ),
    )}
    <rect x={0} y={-150} width={90} height={60} fill="none" stroke={COL.ink} strokeWidth={4} />
    {label && (
      <text x={45} y={30} textAnchor="middle" fontFamily={FONT.title} fontWeight={800} fontSize={30} fill={COL.ink}>
        {label}
      </text>
    )}
  </g>
);

// held weapons: centred on the grip, pointing up (rotate with <At r>)
export const Sword: React.FC = () => (
  <g>
    <rect x={-4} y={-100} width={8} height={96} fill="#d9d9d9" stroke={COL.ink} strokeWidth={4} strokeLinejoin="round" />
    <polygon points="-4,-100 4,-100 0,-116" fill="#d9d9d9" stroke={COL.ink} strokeWidth={4} strokeLinejoin="round" />
    <rect x={-16} y={-6} width={32} height={9} rx={3} fill={COL.gold} stroke={COL.ink} strokeWidth={4} />
    <rect x={-4} y={3} width={8} height={20} rx={3} fill="#5a3a1e" stroke={COL.ink} strokeWidth={4} />
  </g>
);

// rope/web line between two points, with a little sag so it reads as a line under tension
// rather than a ruler; opacity lets you fade it in while it "shoots"
export const WebLine: React.FC<{ x1: number; y1: number; x2: number; y2: number; sag?: number; opacity?: number; color?: string; width?: number }> = ({
  x1,
  y1,
  x2,
  y2,
  sag = 18,
  opacity = 1,
  color = "#f4f4f0",
  width = 3.5,
}) => {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2 + sag;
  return <path d={`M${x1},${y1} Q${mx},${my} ${x2},${y2}`} stroke={color} strokeWidth={width} fill="none" strokeLinecap="round" opacity={opacity} />;
};

// deterministic city-building silhouettes for a static backdrop (two calls at different
// seed/tint/count/height give a cheap far/near parallax read without any actual scrolling):
//   <Skyline seed={1} tint="#aab4c8" count={10} minH={200} maxH={520} /> // far
//   <Skyline seed={2} tint="#2a2f3a" count={7} minH={320} maxH={820} windows /> // near
export const Skyline: React.FC<{ seed?: number; tint?: string; count?: number; minH?: number; maxH?: number; width?: number; windows?: boolean }> = ({
  seed = 0,
  tint = "#2a2f3a",
  count = 10,
  minH = 260,
  maxH = 700,
  width = 1920,
  windows = false,
}) => {
  const rnd = (i: number) => {
    const x = Math.sin(i * 127.1 + seed * 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  const cell = width / count;
  return (
    <g>
      {Array.from({ length: count }).map((_, i) => {
        const h = minH + rnd(i) * (maxH - minH);
        const bw = cell * (0.55 + rnd(i + 50) * 0.35);
        const x = i * cell + (cell - bw) / 2;
        const y = 1080 - h;
        const cols = Math.max(1, Math.floor(bw / 34));
        const rows = Math.max(1, Math.floor(h / 40));
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={h + 20} fill={tint} />
            {windows &&
              Array.from({ length: cols * rows }).map((__, k) => {
                const c = k % cols;
                const r = Math.floor(k / cols);
                if (rnd(i * 97 + k) > 0.4) return null;
                return (
                  <rect
                    key={k}
                    x={x + 14 + c * (bw / cols)}
                    y={y + 18 + r * 40}
                    width={9}
                    height={13}
                    fill="#f2c96d"
                    opacity={0.55 + rnd(i * 13 + k) * 0.35}
                  />
                );
              })}
          </g>
        );
      })}
    </g>
  );
};

export const Lance: React.FC<{ length?: number; pennant?: string }> = ({ length = 260, pennant = COL.red }) => (
  <g>
    <rect x={-4} y={-length} width={8} height={length + 60} rx={3} fill="#8a6a3a" stroke={COL.ink} strokeWidth={4} />
    <polygon points={`-6,${-length} 6,${-length} 0,${-length - 30}`} fill="#d9d9d9" stroke={COL.ink} strokeWidth={4} strokeLinejoin="round" />
    <polygon points={`4,${-length + 8} 44,${-length + 22} 4,${-length + 38}`} fill={pennant} stroke={COL.ink} strokeWidth={3} strokeLinejoin="round" />
  </g>
);

// held longbow: centred on the grip, stave running up/down (rotate with <At r>). `drawn` pulls the
// string back a fixed distance with a nocked arrow; `pull` = [x, y] (local coords, i.e. relative to
// the grip, before <At s>/r) puts the string hand exactly where the draw arm's hand is, so the string
// and arrow follow the pose. Pair with ArrowVolley (weather.tsx) for the actual flight.
export const Bow: React.FC<{ drawn?: boolean; pull?: [number, number]; color?: string }> = ({ drawn = false, pull, color = "#8a6a3a" }) => {
  const p: [number, number] | null = pull ?? (drawn ? [-36, 0] : null);
  const [px, py] = p ?? [-6, 0];
  const n = p ? Math.hypot(px, py) || 1 : 1;
  const tip = p ? [-px / n * (n + 56), -py / n * (n + 56)] : [0, 0];
  return (
    <g>
      <path d="M0,-130 Q34,0 0,130" fill="none" stroke={color} strokeWidth={9} strokeLinecap="round" />
      <path d={`M0,-124 L${px},${py} L0,124`} fill="none" stroke={COL.ink} strokeWidth={3} />
      {p && (
        <g>
          <line x1={px} y1={py} x2={tip[0]} y2={tip[1]} stroke="#d9d9d9" strokeWidth={4} strokeLinecap="round" />
          <circle cx={tip[0]} cy={tip[1]} r={4} fill="#d9d9d9" stroke={COL.ink} strokeWidth={2} />
        </g>
      )}
    </g>
  );
};
