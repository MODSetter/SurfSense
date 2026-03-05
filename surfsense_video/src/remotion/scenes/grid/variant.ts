/**
 * Grid scene variant — seed-deterministic visual style.
 * Each field controls a different visual dimension of the grid cards.
 */
import { random } from "remotion";

type Layout = "vertical" | "horizontal" | "centered";
type ValueStyle = "hero" | "inline" | "badge" | "colored";
type IconStyle = "small" | "large" | "badge";
type SepStyle = "line" | "dots" | "none";
type Align = "left" | "center";

/** SVG stroke reveal animation style. */
type RevealStyle =
  | "drawSingle"   // single stroke traces the full border
  | "drawDouble"   // two strokes race from opposite corners
  | "drawEdges"    // all 4 edges draw independently with stagger
  | "drawBrackets" // L-shaped corner marks snap in
  | "drawNoisy";   // stroke distorted by SVG turbulence

/** Card background fill style. */
export type CardBg =
  | "solid"    // no extra fill, just the glow overlay
  | "glass"    // frosted glass with backdrop blur
  | "gradient" // diagonal gradient tinted with card color
  | "subtle";  // soft radial tint at glow position

export interface GridVariant {
  layout: Layout;
  valueStyle: ValueStyle;
  iconStyle: IconStyle;
  separator: SepStyle;
  align: Align;
  /** Base angle for per-card glow offset (degrees). */
  glowAngle: number;
  reveal: RevealStyle;
  cardBg: CardBg;
}

/** Derive a deterministic variant from a numeric seed. */
export function deriveGridVariant(seed: number): GridVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: "vertical" as Layout,
    valueStyle: pick("value", ["hero", "inline", "badge", "colored"] as ValueStyle[]),
    iconStyle: pick("icon", ["small", "large", "badge"] as IconStyle[]),
    separator: pick("sep", ["line", "dots", "none"] as SepStyle[]),
    align: pick("align", ["left", "center"] as Align[]),
    glowAngle: s("glow") * 360,
    reveal: pick("reveal", [
      "drawSingle", "drawDouble", "drawEdges", "drawBrackets", "drawNoisy",
    ] as RevealStyle[]),
    cardBg: pick("cardBg", [
      "solid", "glass", "gradient", "subtle",
    ] as CardBg[]),
  };
}
