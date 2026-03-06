/** Sequence scene variant — seed-deterministic visual style. */
import { random } from "remotion";

export type SequenceLayout = "steps" | "timeline" | "snake" | "ascending" | "zigzag";
type ItemShape = "rounded" | "pill";
type ArrowStyle = "solid" | "dashed";
export type SequenceCardStyle = "top-bar" | "glow" | "bordered" | "minimal";

export interface SequenceVariant {
  layout: SequenceLayout;
  itemShape: ItemShape;
  arrowStyle: ArrowStyle;
  cardStyle: SequenceCardStyle;
  showStepNumber: boolean;
}

export function deriveSequenceVariant(seed: number): SequenceVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", ["steps", "timeline", "snake", "ascending", "zigzag"] as SequenceLayout[]),
    itemShape: pick("shape", ["rounded", "pill"] as ItemShape[]),
    arrowStyle: pick("arrow", ["solid", "dashed"] as ArrowStyle[]),
    cardStyle: pick("cardStyle", ["top-bar", "glow", "bordered", "minimal"] as SequenceCardStyle[]),
    showStepNumber: s("stepNum") > 0.3,
  };
}
