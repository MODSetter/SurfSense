/** Zod schemas and inferred types for chart scene data. */
import { z } from "zod";

export const ChartItemSchema = z.object({
  label: z.string(),
  value: z.number(),
  color: z.string().optional(),
});

export type ChartItem = z.infer<typeof ChartItemSchema>;

export const ChartSceneInput = z.object({
  type: z.literal("chart"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  xTitle: z.string().optional(),
  yTitle: z.string().optional(),
  items: z.array(ChartItemSchema).min(1),
});

export type ChartSceneInput = z.infer<typeof ChartSceneInput>;
