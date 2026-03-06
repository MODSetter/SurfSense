/** Intro scene variant -- seed-deterministic visual style. */
import { random } from "remotion";

export type IntroAnimation = "fadeUp" | "scaleIn" | "typewriter" | "splitReveal" | "glowIn";
export type IntroBgStyle = "radialGlow" | "gradientSweep" | "particleDots" | "minimal";
export type IntroDecor = "line" | "corners" | "ring" | "none";

export interface IntroVariant {
  animation: IntroAnimation;
  bgStyle: IntroBgStyle;
  decor: IntroDecor;
  accentHue: number;
}

export function deriveIntroVariant(seed: number): IntroVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    animation: pick("anim", [
      "fadeUp", "scaleIn", "typewriter", "splitReveal", "glowIn",
    ] as IntroAnimation[]),
    bgStyle: pick("bg", [
      "radialGlow", "gradientSweep", "particleDots", "minimal",
    ] as IntroBgStyle[]),
    decor: pick("decor", [
      "line", "corners", "ring", "none",
    ] as IntroDecor[]),
    accentHue: Math.floor(s("hue") * 360),
  };
}
