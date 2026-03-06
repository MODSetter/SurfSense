/** Zod schemas and inferred types for list scene data. */
import { z } from "zod";

export const ListItemSchema = z.object({
  label: z.string(),
  desc: z.string().optional(),
  value: z.union([z.string(), z.number()]).optional(),
  color: z.string().optional(),
});

export type ListItem = z.infer<typeof ListItemSchema>;

export const ListSceneInput = z.object({
  type: z.literal("list"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  items: z.array(ListItemSchema).min(1),
});

export type ListSceneInput = z.infer<typeof ListSceneInput>;

/** Positioned list item for rendering. */
export interface LayoutItem {
  data: ListItem;
  x: number;
  y: number;
  w: number;
  h: number;
  index: number;
}

/** Camera stop. */
export interface Waypoint {
  cx: number;
  cy: number;
  holdFrames: number;
  transitionAfter: number;
}
