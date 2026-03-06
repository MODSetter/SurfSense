/**
 * BarChart — horizontal or vertical bars with staggered animated growth.
 * Uses d3-scale for linear value mapping.
 */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import { scaleLinear } from "d3-scale";
import type { ThemeColors } from "../../../theme";
import type { ChartItem } from "../types";
import type { ChartVariant, ChartStyle } from "../variant";
import { ITEM_STAGGER, ITEM_ANIM_DURATION } from "../constants";
import type { BarLayoutInfo } from "../layout";

interface BarChartProps {
  items: ChartItem[];
  chartW: number;
  chartH: number;
  vmin: number;
  variant: ChartVariant;
  theme: ThemeColors;
  isColumn: boolean;
  barLayout: BarLayoutInfo;
}

function barFill(style: ChartStyle, color: string, isColumn: boolean): string {
  switch (style) {
    case "gradient":
      return isColumn
        ? `linear-gradient(180deg, ${color}, ${color}66)`
        : `linear-gradient(90deg, ${color}66, ${color})`;
    case "solid":
      return color;
    case "glass":
      return `${color}55`;
    case "outlined":
      return `${color}20`;
  }
}

export const BarChart: React.FC<BarChartProps> = ({
  items,
  chartW,
  chartH,
  vmin,
  variant,
  theme,
  isColumn,
  barLayout,
}) => {
  const frame = useCurrentFrame();
  const maxVal = Math.max(...items.map((d) => d.value), 1);

  const scale = scaleLinear().domain([0, maxVal]).range([0, 1]);

  const { barThickness, gap } = barLayout;
  const labelFontSize = vmin * 1.8;
  const valueFontSize = vmin * 1.6;
  const labelSpace = isColumn ? vmin * 8 : vmin * 18;
  const valueSpace = variant.showValues ? vmin * 10 : 0;

  const barArea = isColumn ? chartW : chartW - labelSpace - valueSpace;
  const gridLines = variant.showGrid ? [0.25, 0.5, 0.75, 1] : [];

  return (
    <div style={{ position: "relative", width: chartW, height: chartH }}>
      {/* Grid lines */}
      {gridLines.map((frac) => {
        if (isColumn) {
          const y = chartH - labelSpace - (chartH - labelSpace) * frac;
          return (
            <div
              key={frac}
              style={{
                position: "absolute",
                left: 0,
                top: y,
                width: chartW,
                height: 1,
                background: `${theme.textSecondary}20`,
              }}
            />
          );
        }
        const x = labelSpace + barArea * frac;
        return (
          <div
            key={frac}
            style={{
              position: "absolute",
              left: x,
              top: 0,
              width: 1,
              height: chartH,
              background: `${theme.textSecondary}20`,
            }}
          />
        );
      })}

      {items.map((item, i) => {
        const color = item.color ?? "#6c7dff";
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
          [0, ITEM_ANIM_DURATION * 0.5],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );

        const ratio = scale(item.value) * progress;
        const bg = barFill(variant.chartStyle, color, isColumn);
        const borderRadius = vmin * 0.5;

        if (isColumn) {
          const x = i * (barThickness + gap);
          const maxBarH = chartH - labelSpace;
          const barH = maxBarH * ratio;

          return (
            <React.Fragment key={i}>
              <div
                style={{
                  position: "absolute",
                  left: x,
                  bottom: labelSpace,
                  width: barThickness,
                  height: barH,
                  background: bg,
                  borderRadius: `${borderRadius}px ${borderRadius}px 0 0`,
                  border: variant.chartStyle === "outlined" ? `${vmin * 0.15}px solid ${color}` : "none",
                  opacity,
                }}
              />
              {/* Label below */}
              <div
                style={{
                  position: "absolute",
                  left: x,
                  bottom: 0,
                  width: barThickness,
                  height: labelSpace,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  opacity,
                }}
              >
                <span
                  style={{
                    color: theme.textSecondary,
                    fontSize: labelFontSize,
                    fontFamily: "Inter, system-ui, sans-serif",
                    textAlign: "center",
                    lineHeight: 1.2,
                    maxWidth: barThickness,
                    overflow: "hidden",
                  }}
                >
                  {item.label}
                </span>
              </div>
              {/* Value on top */}
              {variant.showValues && (
                <div
                  style={{
                    position: "absolute",
                    left: x,
                    bottom: labelSpace + barH + vmin * 0.5,
                    width: barThickness,
                    textAlign: "center",
                    opacity,
                  }}
                >
                  <span
                    style={{
                      color: theme.textPrimary,
                      fontSize: valueFontSize,
                      fontWeight: 600,
                      fontFamily: "Inter, system-ui, sans-serif",
                    }}
                  >
                    {item.value}
                  </span>
                </div>
              )}
            </React.Fragment>
          );
        }

        // Horizontal bar
        const y = i * (barThickness + gap);
        const barW = barArea * ratio;

        return (
          <React.Fragment key={i}>
            {/* Label on left */}
            <div
              style={{
                position: "absolute",
                left: 0,
                top: y,
                width: labelSpace - vmin,
                height: barThickness,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                opacity,
              }}
            >
              <span
                style={{
                  color: theme.textSecondary,
                  fontSize: labelFontSize,
                  fontFamily: "Inter, system-ui, sans-serif",
                  textAlign: "right",
                  lineHeight: 1.2,
                }}
              >
                {item.label}
              </span>
            </div>
            {/* Bar */}
            <div
              style={{
                position: "absolute",
                left: labelSpace,
                top: y,
                width: barW,
                height: barThickness,
                background: bg,
                borderRadius: `0 ${borderRadius}px ${borderRadius}px 0`,
                border: variant.chartStyle === "outlined" ? `${vmin * 0.15}px solid ${color}` : "none",
                opacity,
              }}
            />
            {/* Value at end */}
            {variant.showValues && (
              <div
                style={{
                  position: "absolute",
                  left: labelSpace + barW + vmin * 0.8,
                  top: y,
                  height: barThickness,
                  display: "flex",
                  alignItems: "center",
                  opacity,
                }}
              >
                <span
                  style={{
                    color: theme.textPrimary,
                    fontSize: valueFontSize,
                    fontWeight: 600,
                    fontFamily: "Inter, system-ui, sans-serif",
                  }}
                >
                  {item.value}
                </span>
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
