/** Relation scene variant — seed-deterministic visual style. */
import { random } from "remotion";

export type RelationLayout = "circle" | "network" | "dagre-tb" | "dagre-lr";
export type RelationCardStyle = "gradient" | "glass" | "outline" | "solid";
export type RelationEdgeStyle = "solid" | "dashed";
export type RelationEdgeColorMode = "solid" | "gradient";

export interface RelationVariant {
  layout: RelationLayout;
  cardStyle: RelationCardStyle;
  edgeStyle: RelationEdgeStyle;
  edgeColorMode: RelationEdgeColorMode;
  showEdgeLabels: boolean;
  showArrows: boolean;
}

export function deriveRelationVariant(seed: number): RelationVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", [
      "circle", "network", "dagre-tb", "dagre-lr",
    ] as RelationLayout[]),
    cardStyle: pick("cardStyle", [
      "gradient", "glass", "outline", "solid",
    ] as RelationCardStyle[]),
    edgeStyle: pick("edgeStyle", ["solid", "dashed"] as RelationEdgeStyle[]),
    edgeColorMode: pick("edgeColor", ["solid", "gradient"] as RelationEdgeColorMode[]),
    showEdgeLabels: s("edgeLabels") > 0.4,
    showArrows: s("arrows") > 0.3,
  };
}
