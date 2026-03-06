/** Zod schemas and inferred types for sequence scene data. */
import { z } from "zod";

export const SequenceItemSchema = z.object({
  label: z.string(),
  desc: z.string().optional(),
  color: z.string().optional(),
});

export type SequenceItem = z.infer<typeof SequenceItemSchema>;

export const SequenceSceneInput = z.object({
  type: z.literal("sequence"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  items: z.array(SequenceItemSchema).min(1),
});

export type SequenceSceneInput = z.infer<typeof SequenceSceneInput>;

/** Positioned sequence item for rendering. */
export interface LayoutItem {
  data: SequenceItem;
  x: number;
  y: number;
  w: number;
  h: number;
  index: number;
}

/** Connector between two items. */
export interface Connector {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  /** Optional SVG path for curved connectors (overrides straight line). */
  curvePath?: string;
  index: number;
}

/** Camera stop. */
export interface Waypoint {
  cx: number;
  cy: number;
  holdFrames: number;
  transitionAfter: number;
}
