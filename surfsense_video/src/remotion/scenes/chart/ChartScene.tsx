/**
 * ChartScene — renders bar, column, pie, donut, or line chart
 * with animated item reveals, camera paging for overflow, and optional title.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { ChartSceneInput } from "./types";
import type { ChartVariant } from "./variant";
import { BarChart } from "./components/BarChart";
import { PieChart } from "./components/PieChart";
import { LineChart } from "./components/LineChart";
import {
  computeBarLayout,
  buildBarWaypoints,
  computeLineLayout,
  buildLineWaypoints,
  type Waypoint,
} from "./layout";

interface ChartSceneProps {
  input: ChartSceneInput;
  theme: ThemeColors;
  variant: ChartVariant;
}

function resolveCamera(waypoints: Waypoint[], frame: number): { cx: number; cy: number } {
  let cam = { cx: waypoints[0].cx, cy: waypoints[0].cy };
  let cursor = 0;

  for (let w = 0; w < waypoints.length; w++) {
    const wp = waypoints[w];
    if (frame < cursor + wp.holdFrames) {
      cam = { cx: wp.cx, cy: wp.cy };
      break;
    }
    cursor += wp.holdFrames;

    if (wp.transitionAfter > 0 && w + 1 < waypoints.length) {
      if (frame < cursor + wp.transitionAfter) {
        const t = Easing.inOut(Easing.ease)(
          (frame - cursor) / wp.transitionAfter,
        );
        const next = waypoints[w + 1];
        cam = {
          cx: wp.cx + (next.cx - wp.cx) * t,
          cy: wp.cy + (next.cy - wp.cy) * t,
        };
        break;
      }
      cursor += wp.transitionAfter;
    }

    if (w === waypoints.length - 1) {
      cam = { cx: wp.cx, cy: wp.cy };
    }
  }

  return cam;
}

export const ChartScene: React.FC<ChartSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const { width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;
  const frame = useCurrentFrame();

  const titleH = input.title ? vmin * 12 : vmin * 4;
  const pad = vmin * 10;
  const chartW = width - pad * 2;
  const chartH = height - titleH - pad * 1.2;

  const isBar = variant.layout === "bar" || variant.layout === "column";
  const isCol = variant.layout === "column";
  const isLine = variant.layout === "line";

  const { barLayout, lineLayout, waypoints } = useMemo(() => {
    if (isBar) {
      const availableSize = isCol ? chartW : chartH;
      const bl = computeBarLayout(input.items.length, availableSize, vmin);
      const wps = buildBarWaypoints(input.items.length, bl, availableSize, isCol);
      return { barLayout: bl, lineLayout: undefined, waypoints: wps };
    }

    if (isLine) {
      const ll = computeLineLayout(input.items.length, chartW, vmin);
      const wps = buildLineWaypoints(ll, chartW);
      return { barLayout: undefined, lineLayout: ll, waypoints: wps };
    }

    return { barLayout: undefined, lineLayout: undefined, waypoints: undefined };
  }, [isBar, isCol, isLine, chartW, chartH, input.items.length, vmin]);

  const cam = waypoints ? resolveCamera(waypoints, frame) : { cx: 0, cy: 0 };

  let chartOffsetX = 0;
  let chartOffsetY = 0;

  if (isBar && waypoints) {
    if (isCol) {
      chartOffsetX = chartW / 2 - cam.cx;
    } else {
      chartOffsetY = chartH / 2 - cam.cy;
    }
  } else if (isLine && waypoints) {
    chartOffsetX = chartW / 2 - cam.cx;
  }

  const containerW = isCol && barLayout?.overflow
    ? barLayout.totalSize
    : isLine && lineLayout?.overflow
      ? lineLayout.totalW + vmin * 8
      : chartW;

  const containerH = !isCol && isBar && barLayout?.overflow
    ? barLayout.totalSize
    : chartH;

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      {input.title && (
        <div
          style={{
            position: "absolute",
            top: vmin * 3,
            left: 0,
            width: "100%",
            textAlign: "center",
            zIndex: 10,
          }}
        >
          <div
            style={{
              color: theme.textPrimary,
              fontSize: vmin * 3.5,
              fontWeight: 700,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {input.title}
          </div>
          {input.subtitle && (
            <div
              style={{
                color: theme.textSecondary,
                fontSize: vmin * 1.8,
                fontFamily: "Inter, system-ui, sans-serif",
                marginTop: vmin * 0.5,
              }}
            >
              {input.subtitle}
            </div>
          )}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          left: pad + chartOffsetX,
          top: titleH + chartOffsetY,
          width: containerW,
          height: containerH,
          overflow: "visible",
        }}
      >
        {isBar && barLayout && (
          <BarChart
            items={input.items}
            chartW={isCol && barLayout.overflow ? barLayout.totalSize : chartW}
            chartH={!isCol && barLayout.overflow ? barLayout.totalSize : chartH}
            vmin={vmin}
            variant={variant}
            theme={theme}
            isColumn={isCol}
            barLayout={barLayout}
          />
        )}
        {(variant.layout === "pie" || variant.layout === "donut") && (
          <PieChart
            items={input.items}
            chartW={chartW}
            chartH={chartH}
            vmin={vmin}
            variant={variant}
            theme={theme}
            isDonut={variant.layout === "donut"}
          />
        )}
        {isLine && (
          <LineChart
            items={input.items}
            chartW={chartW}
            chartH={chartH}
            vmin={vmin}
            variant={variant}
            theme={theme}
            lineLayout={lineLayout}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
