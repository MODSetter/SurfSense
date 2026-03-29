import { z } from "zod";

export const AspectRatioSchema = z
  .enum(["auto", "1:1", "4:3", "16:9", "9:16"])
  .default("auto");

export type AspectRatio = z.infer<typeof AspectRatioSchema>;

export const MediaFitSchema = z.enum(["cover", "contain"]).default("cover");

export type MediaFit = z.infer<typeof MediaFitSchema>;

export const RATIO_CLASS_MAP: Record<AspectRatio, string> = {
  auto: "",
  "1:1": "aspect-square",
  "4:3": "aspect-[4/3]",
  "16:9": "aspect-video",
  "9:16": "aspect-[9/16]",
};

export function getRatioClass(ratio: AspectRatio): string {
  return RATIO_CLASS_MAP[ratio];
}

export function getFitClass(fit: MediaFit): string {
  return fit === "cover" ? "object-cover" : "object-contain";
}
