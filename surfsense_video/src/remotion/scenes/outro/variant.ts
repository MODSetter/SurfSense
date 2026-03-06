/** Outro scene variant -- seed-deterministic visual style. */
import { random } from "remotion";

export type OutroAnimation = "fadeCenter" | "shrinkOut" | "slideUp" | "dissolve" | "wipeOut";
export type OutroBgStyle = "radialGlow" | "gradientSweep" | "vignette" | "minimal";
export type OutroDecor = "line" | "ring" | "particles" | "none";

export interface OutroVariant {
  animation: OutroAnimation;
  bgStyle: OutroBgStyle;
  decor: OutroDecor;
  accentHue: number;
}

export function deriveOutroVariant(seed: number): OutroVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    animation: pick("anim", [
      "fadeCenter", "shrinkOut", "slideUp", "dissolve", "wipeOut",
    ] as OutroAnimation[]),
    bgStyle: pick("bg", [
      "radialGlow", "gradientSweep", "vignette", "minimal",
    ] as OutroBgStyle[]),
    decor: pick("decor", [
      "line", "ring", "particles", "none",
    ] as OutroDecor[]),
    accentHue: Math.floor(s("hue") * 360),
  };
}
