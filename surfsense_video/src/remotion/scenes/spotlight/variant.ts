/** Spotlight scene variant — seed-deterministic visual style. */
import { random } from "remotion";

type RevealStyle =
  | "drawSingle"
  | "drawDouble"
  | "drawEdges"
  | "drawBrackets"
  | "drawNoisy";

export type SpotlightCardBg = "solid" | "glass" | "gradient" | "subtle";
export type SpotlightValueStyle = "hero" | "inline" | "badge" | "colored";

export interface SpotlightVariant {
  cardBg: SpotlightCardBg;
  valueStyle: SpotlightValueStyle;
  reveal: RevealStyle;
  glowAngle: number;
}

export function deriveSpotlightVariant(seed: number): SpotlightVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    cardBg: pick("cardBg", [
      "solid", "glass", "gradient", "subtle",
    ] as SpotlightCardBg[]),
    valueStyle: pick("value", [
      "hero", "inline", "badge", "colored",
    ] as SpotlightValueStyle[]),
    reveal: pick("reveal", [
      "drawSingle", "drawDouble", "drawEdges", "drawBrackets", "drawNoisy",
    ] as RevealStyle[]),
    glowAngle: s("glow") * 360,
  };
}
