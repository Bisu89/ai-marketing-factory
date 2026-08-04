import { useState } from "react";
import "./BarRanking.css";

export interface BarRankingItem {
  label: string;
  value: number;
}

interface BarRankingProps {
  items: BarRankingItem[];
  formatValue?: (value: number) => string;
  emptyText?: string;
}

// Single-series magnitude ranking (compare views/etc across categories) --
// one accent hue, no categorical palette needed since axis labels already
// carry identity. Per the dataviz skill: bar/magnitude jobs get a sequential
// (one-hue) treatment, not a categorical rainbow.
export function BarRanking({ items, formatValue = (v) => v.toLocaleString("vi-VN"), emptyText = "Chưa có dữ liệu" }: BarRankingProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (items.length === 0) {
    return <div className="bar-ranking-empty">{emptyText}</div>;
  }

  const maxValue = Math.max(...items.map((i) => i.value), 1);

  return (
    <div className="bar-ranking">
      {items.map((item, i) => (
        <div
          key={item.label}
          className="bar-ranking-row"
          onMouseEnter={() => setHoverIndex(i)}
          onMouseLeave={() => setHoverIndex(null)}
        >
          <span className="bar-ranking-label" title={item.label}>
            {item.label}
          </span>
          <div className="bar-ranking-track">
            <div
              className="bar-ranking-fill"
              style={{ width: `${Math.max((item.value / maxValue) * 100, 2)}%` }}
            />
          </div>
          <span className="bar-ranking-value">{formatValue(item.value)}</span>
          {hoverIndex === i && (
            <div className="bar-ranking-tooltip">
              {item.label}: {formatValue(item.value)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
