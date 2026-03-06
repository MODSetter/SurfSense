/** Remotion Studio compositions for chart scene. */
import React from "react";
import { Composition } from "remotion";
import { ChartScene } from "./ChartScene";
import { THEMES } from "../../theme";
import type { ChartVariant, ChartLayout } from "./variant";
import { DEMO_CHART, DEMO_CHART_LARGE, DEMO_CHART_XL } from "./demo";
import { chartSceneDuration } from "./layout";

const THEME = "dark" as const;
const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

const vmin = Math.min(WIDTH, HEIGHT) / 100;

const ChartPreview: React.FC<{ variant: ChartVariant; data?: typeof DEMO_CHART }> = ({
  variant,
  data = DEMO_CHART,
}) => {
  const theme = THEMES[THEME];
  return <ChartScene input={data} theme={theme} variant={variant} />;
};

const layouts: ChartLayout[] = ["bar", "column", "pie", "donut", "line"];

const base: ChartVariant = {
  layout: "bar",
  chartStyle: "gradient",
  showValues: true,
  showGrid: true,
};

function dur(itemCount: number, layout: ChartLayout) {
  return chartSceneDuration(itemCount, layout, WIDTH, HEIGHT, vmin);
}

export const chartPreviews = (
  <>
    {/* Standard (7 items) — all layouts */}
    {layouts.map((layout) => {
      const v: ChartVariant = { ...base, layout };
      return (
        <Composition
          key={layout}
          id={`chart-${layout}`}
          component={() => <ChartPreview variant={v} />}
          durationInFrames={dur(DEMO_CHART.items.length, layout)}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      );
    })}
    <Composition
      id="chart-bar-outlined"
      component={() => (
        <ChartPreview variant={{ ...base, chartStyle: "outlined" }} />
      )}
      durationInFrames={dur(DEMO_CHART.items.length, "bar")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="chart-pie-glass"
      component={() => (
        <ChartPreview variant={{ ...base, layout: "pie", chartStyle: "glass" }} />
      )}
      durationInFrames={dur(DEMO_CHART.items.length, "pie")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* Large (20 items) — bar overflows, camera pans vertically */}
    <Composition
      id="chart-bar-large"
      component={() => (
        <ChartPreview variant={base} data={DEMO_CHART_LARGE} />
      )}
      durationInFrames={dur(DEMO_CHART_LARGE.items.length, "bar")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* XL (35 items) — column overflows horizontally, camera pans */}
    <Composition
      id="chart-column-xl"
      component={() => (
        <ChartPreview variant={{ ...base, layout: "column" }} data={DEMO_CHART_XL} />
      )}
      durationInFrames={dur(DEMO_CHART_XL.items.length, "column")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* XL (35 items) — line overflows horizontally, camera pans */}
    <Composition
      id="chart-line-xl"
      component={() => (
        <ChartPreview variant={{ ...base, layout: "line" }} data={DEMO_CHART_XL} />
      )}
      durationInFrames={dur(DEMO_CHART_XL.items.length, "line")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />

    {/* XL bar — 35 items, horizontal bar with heavy paging */}
    <Composition
      id="chart-bar-xl"
      component={() => (
        <ChartPreview variant={base} data={DEMO_CHART_XL} />
      )}
      durationInFrames={dur(DEMO_CHART_XL.items.length, "bar")}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
