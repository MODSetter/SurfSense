import { z } from "zod";
import { GridSceneInput } from "./scenes/grid/types";

export const Theme = z.enum(["dark", "light"]);

export const SceneInput = z.discriminatedUnion("type", [GridSceneInput]);

export const VideoInput = z.object({
  generationSeed: z.number().int(),
  theme: Theme,
  scenes: z.array(SceneInput).min(1),
});

export type Theme = z.infer<typeof Theme>;
export type SceneInput = z.infer<typeof SceneInput>;
export type VideoInput = z.infer<typeof VideoInput>;
