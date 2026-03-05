/** Zod schemas and inferred types for hierarchy (tree) scene data. */
import { z } from "zod";

export interface HierarchyNode {
  label: string;
  color?: string;
  desc?: string;
  children?: HierarchyNode[];
}

const HierarchyNodeSchema: z.ZodType<HierarchyNode> = z.object({
  label: z.string(),
  color: z.string().optional(),
  desc: z.string().optional(),
  children: z.lazy(() => z.array(HierarchyNodeSchema)).optional(),
});

export { HierarchyNodeSchema };

export const HierarchySceneInput = z.object({
  type: z.literal("hierarchy"),
  title: z.string().optional(),
  items: z.array(HierarchyNodeSchema).min(1),
});

export type HierarchySceneInput = z.infer<typeof HierarchySceneInput>;

/** Flattened d3 hierarchy node with layout coordinates. */
export interface LayoutNode {
  data: HierarchyNode;
  x: number;
  y: number;
  depth: number;
  parent: LayoutNode | null;
  children?: LayoutNode[];
  siblingIndex: number;
}

/** Camera stop — position + hold duration + transition to next. */
export interface Waypoint {
  cx: number;
  cy: number;
  holdFrames: number;
  transitionAfter: number;
  depth: number;
}
