/** Comparison scene variant — seed-deterministic visual style. */
import { random } from "remotion";

export type ComparisonLayout = "binary" | "table";
export type ComparisonCardStyle = "gradient" | "glass" | "outline" | "solid";
export type ComparisonDivider = "vs" | "line" | "none";

export interface ComparisonVariant {
  layout: ComparisonLayout;
  cardStyle: ComparisonCardStyle;
  divider: ComparisonDivider;
}

export function deriveComparisonVariant(seed: number): ComparisonVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", [
      "binary", "table",
    ] as ComparisonLayout[]),
    cardStyle: pick("cardStyle", [
      "gradient", "glass", "outline", "solid",
    ] as ComparisonCardStyle[]),
    divider: pick("divider", ["vs", "line", "none"] as ComparisonDivider[]),
  };
}
