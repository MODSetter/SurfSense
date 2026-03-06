import { z } from "zod";
import { SpotlightSceneInput } from "./scenes/spotlight/types";
import { HierarchySceneInput } from "./scenes/hierarchy/types";
import { ListSceneInput } from "./scenes/list/types";
import { SequenceSceneInput } from "./scenes/sequence/types";
import { ChartSceneInput } from "./scenes/chart/types";
import { RelationSceneInput } from "./scenes/relation/types";
import { ComparisonSceneInput } from "./scenes/comparison/types";

export const SceneInput = z.discriminatedUnion("type", [
  SpotlightSceneInput,
  HierarchySceneInput,
  ListSceneInput,
  SequenceSceneInput,
  ChartSceneInput,
  RelationSceneInput,
  ComparisonSceneInput,
]);

export const VideoInput = z.object({
  generationSeed: z.number().int(),
  scenes: z.array(SceneInput).min(1),
});

export type SceneInput = z.infer<typeof SceneInput>;
export type VideoInput = z.infer<typeof VideoInput>;
