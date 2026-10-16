import { useId } from "react";

import "./components.css";

export interface ChartDatum {
  label: string;
  value: number;
}

interface BarChartProps {
  data: ChartDatum[];
  unit?: string;
  height?: number;
  color?: string;
  emptyLabel?: string;
}

/** Horizontal bar chart with accessible labels, units, and an empty state. */
export function BarChart({
  data,
  unit = "",
  color = "var(--accent)",
  emptyLabel = "No data in this window.",
}: BarChartProps) {
  if (data.length === 0) {
    return <p className="chart-empty">{emptyLabel}</p>;
  }
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="bar-chart" role="img" aria-label="Bar chart">
      {data.map((datum) => {
        const pct = (datum.value / max) * 100;
        return (
          <div className="bar-row" key={datum.label}>
            <span className="bar-label truncate" title={datum.label}>
              {datum.label}
            </span>
            <span className="bar-track">
              <span
                className="bar-fill"
                style={{ width: `${pct}%`, background: color }}
                aria-hidden="true"
              />
            </span>
            <span className="bar-value mono">
              {datum.value}
              {unit ? ` ${unit}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface LineChartProps {
  data: ChartDatum[];
  unit?: string;
  height?: number;
  color?: string;
  emptyLabel?: string;
}

/** Compact SVG line chart for time-ordered series. */
export function LineChart({
  data,
  unit = "",
  height = 140,
  color = "var(--accent)",
  emptyLabel = "No data in this window.",
}: LineChartProps) {
  const gradientId = useId();
  if (data.length === 0) {
    return <p className="chart-empty">{emptyLabel}</p>;
  }
  const width = 640;
  const padding = { top: 12, right: 12, bottom: 22, left: 30 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const max = Math.max(...data.map((d) => d.value), 1);
  const stepX = data.length > 1 ? innerW / (data.length - 1) : 0;
  const points = data.map((d, i) => {
    const x = padding.left + i * stepX;
    const y = padding.top + innerH - (d.value / max) * innerH;
    return { x, y, ...d };
  });
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath = `${path} L ${points[points.length - 1]!.x} ${
    padding.top + innerH
  } L ${points[0]!.x} ${padding.top + innerH} Z`;

  return (
    <svg
      className="line-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Line chart${unit ? ` (${unit})` : ""}`}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 0.5, 1].map((frac) => {
        const y = padding.top + innerH * frac;
        return (
          <line
            key={frac}
            x1={padding.left}
            x2={width - padding.right}
            y1={y}
            y2={y}
            className="chart-gridline"
          />
        );
      })}
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="2" />
      {points.map((p) => (
        <circle key={`${p.label}-${p.x}`} cx={p.x} cy={p.y} r="2.5" fill={color} />
      ))}
      <text x={padding.left - 6} y={padding.top + 4} className="chart-axis" textAnchor="end">
        {max}
      </text>
      <text
        x={padding.left - 6}
        y={padding.top + innerH}
        className="chart-axis"
        textAnchor="end"
      >
        0
      </text>
      {unit && (
        <text x={padding.left} y={height - 6} className="chart-axis">
          {unit}
        </text>
      )}
    </svg>
  );
}

/** Tiny inline sparkline for status tiles. */
export function Sparkline({
  values,
  color = "var(--accent)",
  width = 120,
  height = 28,
}: {
  values: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const path = values
    .map((value, i) => {
      const x = i * stepX;
      const y = height - ((value - min) / range) * height;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden="true" className="sparkline">
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}
