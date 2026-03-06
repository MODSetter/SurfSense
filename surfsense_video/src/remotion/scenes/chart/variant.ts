/** Chart scene variant — seed-deterministic visual style. */
import { random } from "remotion";

export type ChartLayout = "bar" | "column" | "pie" | "donut" | "line";
export type ChartStyle = "gradient" | "solid" | "glass" | "outlined";

export interface ChartVariant {
  layout: ChartLayout;
  chartStyle: ChartStyle;
  showValues: boolean;
  showGrid: boolean;
}

export function deriveChartVariant(seed: number): ChartVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", ["bar", "column", "pie", "donut", "line"] as ChartLayout[]),
    chartStyle: pick("chartStyle", ["gradient", "solid", "glass", "outlined"] as ChartStyle[]),
    showValues: s("values") > 0.3,
    showGrid: s("grid") > 0.4,
  };
}
