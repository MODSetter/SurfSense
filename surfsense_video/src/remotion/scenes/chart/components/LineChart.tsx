/**
 * LineChart — animated line with data points and optional area fill.
 * Uses d3-scale for axis mapping and d3-shape for curve generation.
 * Supports overflow: when lineLayout.overflow is true, the chart is wider
 * than the viewport and ChartScene pans the camera horizontally.
 */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { scaleLinear, scalePoint } from "d3-scale";
import { line as d3Line, area as d3Area, curveMonotoneX } from "d3-shape";
import type { ThemeColors } from "../../../theme";
import type { ChartItem } from "../types";
import type { ChartVariant, ChartStyle } from "../variant";
import { ITEM_STAGGER, ITEM_ANIM_DURATION } from "../constants";
import type { LineLayoutInfo } from "../layout";

interface LineChartProps {
  items: ChartItem[];
  chartW: number;
  chartH: number;
  vmin: number;
  variant: ChartVariant;
  theme: ThemeColors;
  lineLayout?: LineLayoutInfo;
}

function lineColor(style: ChartStyle, color: string): string {
  switch (style) {
    case "gradient":
    case "solid":
      return color;
    case "glass":
      return `${color}cc`;
    case "outlined":
      return color;
  }
}

export const LineChart: React.FC<LineChartProps> = ({
  items,
  chartW,
  chartH,
  vmin,
  variant,
  theme,
  lineLayout,
}) => {
  const frame = useCurrentFrame();
  const padL = vmin * 4;
  const padR = vmin * 4;
  const padT = vmin * 5;
  const padB = vmin * 8;

  const renderW = lineLayout?.overflow ? lineLayout.totalW + padL + padR : chartW;
  const plotW = renderW - padL - padR;
  const plotH = chartH - padT - padB;

  const maxVal = Math.max(...items.map((d) => d.value), 1);
  const minVal = Math.min(...items.map((d) => d.value), 0);
  const yRange = maxVal - minVal || 1;

  const xScale = scalePoint<number>()
    .domain(items.map((_, i) => i))
    .range([0, plotW]);

  const yScale = scaleLinear()
    .domain([minVal - yRange * 0.1, maxVal + yRange * 0.1])
    .range([plotH, 0]);

  const points = items.map((d, i) => ({
    x: (xScale(i) ?? 0) + padL,
    y: yScale(d.value) + padT,
    item: d,
    index: i,
  }));

  const primaryColor = items[0]?.color ?? "#6c7dff";
  const strokeColor = lineColor(variant.chartStyle, primaryColor);

  const lineGen = d3Line<(typeof points)[number]>()
    .x((d) => d.x)
    .y((d) => d.y)
    .curve(curveMonotoneX);

  const areaGen = d3Area<(typeof points)[number]>()
    .x((d) => d.x)
    .y0(padT + plotH)
    .y1((d) => d.y)
    .curve(curveMonotoneX);

  const totalPoints = points.length;
  const totalAnimFrames = (totalPoints - 1) * ITEM_STAGGER + ITEM_ANIM_DURATION;

  const lineProgress = interpolate(
    frame,
    [0, totalAnimFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const linePath = lineGen(points) ?? "";
  const areaPath = areaGen(points) ?? "";

  const gridLines = variant.showGrid ? [0.25, 0.5, 0.75] : [];
  const labelFontSize = vmin * 1.6;
  const valueFontSize = vmin * 1.5;
  const gradientId = "line-area-grad";
  const showArea = variant.chartStyle !== "outlined";

  return (
    <svg width={renderW} height={chartH} style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={primaryColor} stopOpacity={0.3} />
          <stop offset="100%" stopColor={primaryColor} stopOpacity={0.02} />
        </linearGradient>
        <clipPath id="line-reveal">
          <rect x={0} y={0} width={renderW * lineProgress} height={chartH} />
        </clipPath>
      </defs>

      {/* Grid */}
      {gridLines.map((frac) => {
        const y = padT + plotH * (1 - frac);
        return (
          <line
            key={frac}
            x1={padL}
            y1={y}
            x2={padL + plotW}
            y2={y}
            stroke={`${theme.textSecondary}18`}
            strokeWidth={1}
          />
        );
      })}

      {/* Area fill */}
      {showArea && (
        <path
          d={areaPath}
          fill={`url(#${gradientId})`}
          clipPath="url(#line-reveal)"
        />
      )}

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={strokeColor}
        strokeWidth={vmin * 0.25}
        strokeLinecap="round"
        strokeLinejoin="round"
        clipPath="url(#line-reveal)"
      />

      {/* Data points + labels */}
      {points.map((pt, i) => {
        const color = pt.item.color ?? primaryColor;
        const enterF = i * ITEM_STAGGER;
        const localFrame = frame - enterF;

        const opacity = interpolate(
          localFrame,
          [0, ITEM_ANIM_DURATION * 0.5],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        const dotR = vmin * 0.6;

        return (
          <g key={i} opacity={opacity}>
            <circle
              cx={pt.x}
              cy={pt.y}
              r={dotR}
              fill={variant.chartStyle === "outlined" ? "transparent" : color}
              stroke={color}
              strokeWidth={vmin * 0.15}
            />
            {variant.showValues && (
              <text
                x={pt.x}
                y={pt.y - vmin * 1.5}
                textAnchor="middle"
                fill={theme.textPrimary}
                fontSize={valueFontSize}
                fontWeight={600}
                fontFamily="Inter, system-ui, sans-serif"
              >
                {pt.item.value}
              </text>
            )}
            <text
              x={pt.x}
              y={padT + plotH + vmin * 2.5}
              textAnchor="middle"
              fill={theme.textSecondary}
              fontSize={labelFontSize}
              fontFamily="Inter, system-ui, sans-serif"
            >
              {pt.item.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};
