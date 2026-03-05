/** Hierarchy scene variant — seed-deterministic visual style. */
import { random } from "remotion";

type Orientation = "top-bottom" | "left-right";
type EdgeType = "curved" | "straight";
type EdgeColorMode = "solid" | "gradient";
type NodeShape = "rounded" | "pill";

export interface HierarchyVariant {
  orientation: Orientation;
  edgeType: EdgeType;
  edgeColorMode: EdgeColorMode;
  nodeShape: NodeShape;
  edgeCornerRadius: number;
}

export function deriveHierarchyVariant(seed: number): HierarchyVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    orientation: pick("orient", ["top-bottom", "left-right"] as Orientation[]),
    edgeType: pick("edge", ["curved", "straight"] as EdgeType[]),
    edgeColorMode: pick("edgeColor", ["solid", "gradient"] as EdgeColorMode[]),
    nodeShape: pick("shape", ["rounded", "pill"] as NodeShape[]),
    /** Multiplier of vmin — resolved to pixels at render time. */
    edgeCornerRadius: s("corner") * 1.2 + 0.4,
  };
}
