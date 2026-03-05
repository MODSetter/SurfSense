import { random } from "remotion";

type Layout = "vertical" | "horizontal" | "centered";
type AccentSide = "left" | "top" | "bottom" | "right";
type ValueStyle = "hero" | "inline" | "badge" | "colored";
type IconStyle = "small" | "large" | "badge";
type SepStyle = "line" | "dots" | "none";
type Align = "left" | "center";
type RevealStyle = "drawing" | "instant" | "fade";

export interface GridVariant {
  layout: Layout;
  accent: AccentSide;
  valueStyle: ValueStyle;
  iconStyle: IconStyle;
  separator: SepStyle;
  align: Align;
  glowAngle: number;
  reveal: RevealStyle;
}

export function deriveGridVariant(seed: number): GridVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", ["vertical", "horizontal", "centered"] as Layout[]),
    accent: pick("accent", ["left", "top", "bottom", "right"] as AccentSide[]),
    valueStyle: pick("value", ["hero", "inline", "badge", "colored"] as ValueStyle[]),
    iconStyle: pick("icon", ["small", "large", "badge"] as IconStyle[]),
    separator: pick("sep", ["line", "dots", "none"] as SepStyle[]),
    align: pick("align", ["left", "center"] as Align[]),
    glowAngle: s("glow") * 360,
    reveal: pick("reveal", ["drawing", "instant", "fade"] as RevealStyle[]),
  };
}
