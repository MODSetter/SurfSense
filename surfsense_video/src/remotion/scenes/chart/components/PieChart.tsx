/**
 * PieChart — animated arc segments with labels.
 * Uses d3-shape pie() and arc() generators.
 * Supports donut mode via innerRadius.
 */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { pie as d3Pie, arc as d3Arc } from "d3-shape";
import type { ThemeColors } from "../../../theme";
import type { ChartItem } from "../types";
import type { ChartVariant, ChartStyle } from "../variant";
import { ITEM_STAGGER, ITEM_ANIM_DURATION } from "../constants";

interface PieChartProps {
  items: ChartItem[];
  chartW: number;
  chartH: number;
  vmin: number;
  variant: ChartVariant;
  theme: ThemeColors;
  isDonut: boolean;
}

function sliceFill(style: ChartStyle, color: string): string {
  switch (style) {
    case "gradient":
    case "solid":
      return color;
    case "glass":
      return `${color}88`;
    case "outlined":
      return `${color}20`;
  }
}

function sliceStroke(style: ChartStyle, color: string): string | undefined {
  if (style === "outlined") return color;
  if (style === "glass") return `${color}cc`;
  return undefined;
}

export const PieChart: React.FC<PieChartProps> = ({
  items,
  chartW,
  chartH,
  vmin,
  variant,
  theme,
  isDonut,
}) => {
  const frame = useCurrentFrame();
  const size = Math.min(chartW, chartH);
  const radius = size / 2 - vmin * 6;
  const innerR = isDonut ? radius * 0.55 : 0;
  const cx = chartW / 2;
  const cy = chartH / 2;

  const pieGen = d3Pie<ChartItem>()
    .value((d) => d.value)
    .sort(null)
    .padAngle(vmin * 0.006);

  const arcs = pieGen(items);

  const arcGen = d3Arc<(typeof arcs)[number]>()
    .innerRadius(innerR)
    .outerRadius(radius)
    .cornerRadius(vmin * 0.4);

  const labelRadius = radius + vmin * 4;
  const labelFontSize = vmin * 1.8;
  const valueFontSize = vmin * 1.5;
  const total = items.reduce((s, d) => s + d.value, 0);

  return (
    <svg width={chartW} height={chartH} style={{ overflow: "visible" }}>
      {arcs.map((d, i) => {
        const color = d.data.color ?? "#6c7dff";
        const enterF = i * ITEM_STAGGER;
        const localFrame = frame - enterF;

        const progress = interpolate(
          localFrame,
          [0, ITEM_ANIM_DURATION],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        const opacity = interpolate(
          localFrame,
          [0, ITEM_ANIM_DURATION * 0.4],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        const animatedArc = {
          ...d,
          endAngle: d.startAngle + (d.endAngle - d.startAngle) * progress,
        };

        const path = arcGen(animatedArc) ?? "";
        const midAngle = (d.startAngle + d.endAngle) / 2;
        const lx = Math.cos(midAngle - Math.PI / 2) * labelRadius;
        const ly = Math.sin(midAngle - Math.PI / 2) * labelRadius;
        const isRight = lx > 0;
        const fill = sliceFill(variant.chartStyle, color);
        const stroke = sliceStroke(variant.chartStyle, color);
        const pct = total > 0 ? Math.round((d.data.value / total) * 100) : 0;

        return (
          <g key={i} transform={`translate(${cx},${cy})`} opacity={opacity}>
            <path
              d={path}
              fill={fill}
              stroke={stroke}
              strokeWidth={stroke ? vmin * 0.15 : 0}
            />
            {/* Label line + text */}
            {progress > 0.5 && (
              <>
                <line
                  x1={Math.cos(midAngle - Math.PI / 2) * (radius + vmin * 0.5)}
                  y1={Math.sin(midAngle - Math.PI / 2) * (radius + vmin * 0.5)}
                  x2={lx}
                  y2={ly}
                  stroke={`${theme.textSecondary}50`}
                  strokeWidth={vmin * 0.08}
                />
                <text
                  x={lx + (isRight ? vmin * 0.8 : -vmin * 0.8)}
                  y={ly}
                  textAnchor={isRight ? "start" : "end"}
                  dominantBaseline="middle"
                  fill={theme.textSecondary}
                  fontSize={labelFontSize}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {d.data.label}
                </text>
                {variant.showValues && (
                  <text
                    x={lx + (isRight ? vmin * 0.8 : -vmin * 0.8)}
                    y={ly + labelFontSize * 1.2}
                    textAnchor={isRight ? "start" : "end"}
                    dominantBaseline="middle"
                    fill={theme.textPrimary}
                    fontSize={valueFontSize}
                    fontWeight={600}
                    fontFamily="Inter, system-ui, sans-serif"
                  >
                    {d.data.value} ({pct}%)
                  </text>
                )}
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
};
