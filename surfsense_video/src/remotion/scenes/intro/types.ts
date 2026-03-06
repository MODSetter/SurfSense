/** Zod schema and types for intro scene. */
import { z } from "zod";

export const IntroSceneInput = z.object({
  type: z.literal("intro"),
  title: z.string(),
  subtitle: z.string().optional(),
});

export type IntroSceneInput = z.infer<typeof IntroSceneInput>;
