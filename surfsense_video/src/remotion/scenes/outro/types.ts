/** Zod schema and types for outro scene. */
import { z } from "zod";

export const OutroSceneInput = z.object({
  type: z.literal("outro"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
});

export type OutroSceneInput = z.infer<typeof OutroSceneInput>;
