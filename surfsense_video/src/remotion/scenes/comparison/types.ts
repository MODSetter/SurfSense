/** Zod schemas and inferred types for comparison scene data. */
import { z } from "zod";

export const CompareItemSchema = z.object({
  label: z.string(),
  desc: z.string().optional(),
});

export type CompareItem = z.infer<typeof CompareItemSchema>;

export const CompareGroupSchema = z.object({
  label: z.string(),
  color: z.string().optional(),
  items: z.array(CompareItemSchema).min(1),
});

export type CompareGroup = z.infer<typeof CompareGroupSchema>;

export const ComparisonSceneInput = z.object({
  type: z.literal("comparison"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  groups: z.array(CompareGroupSchema).min(2),
});

export type ComparisonSceneInput = z.infer<typeof ComparisonSceneInput>;

/** Camera stop. */
export interface Waypoint {
  cx: number;
  cy: number;
  holdFrames: number;
  transitionAfter: number;
}
