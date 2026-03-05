/**
 * Tree layout utilities — d3 layout, node flattening, camera waypoints.
 */
import { hierarchy, tree } from "d3-hierarchy";
import type { HierarchyNode, HierarchySceneInput, LayoutNode, Waypoint } from "./types";
import { STOP_HOLD, STOP_TRANSITION, LEVEL_TRANSITION } from "./constants";
import { getMaxNodeSize } from "./components/nodeSize";

/** Merge multiple root items into a single root. */
export function normalizeToSingleRoot(items: HierarchyNode[]): HierarchyNode {
  if (items.length === 1) return items[0];
  const [first, ...rest] = items;
  return {
    ...first,
    children: [...(first.children ?? []), ...rest],
  };
}

/** Flatten d3 hierarchy nodes and attach sibling index + parent refs. */
export function flattenNodes(
  root: ReturnType<typeof hierarchy<HierarchyNode>>,
): LayoutNode[] {
  const result: LayoutNode[] = [];
  root.each((d) => {
    const siblings = d.parent?.children ?? [d];
    const sibIdx = siblings.indexOf(d);
    result.push({
      data: d.data,
      x: (d as any).x as number,
      y: (d as any).y as number,
      depth: d.depth,
      parent: null,
      siblingIndex: sibIdx,
    });
  });
  root.each((d, i) => {
    if (d.parent) {
      const parentIdx = result.findIndex(
        (n) => n.data === d.parent!.data && n.depth === d.parent!.depth,
      );
      if (parentIdx >= 0) result[i].parent = result[parentIdx];
    }
  });
  return result;
}

/**
 * Build camera waypoints for a given hierarchy layout.
 * Each depth level gets one or more stops; stops within a level
 * use STOP_TRANSITION, levels use LEVEL_TRANSITION.
 */
export function buildWaypoints(
  nodes: LayoutNode[],
  isHoriz: boolean,
  crossSize: number,
  viewW: number,
  viewH: number,
  maxDepth: number,
): Waypoint[] {
  const viewCross = isHoriz ? viewH : viewW;
  const cellHalf = crossSize / 2;

  const byDepth = new Map<number, { mainPos: number; crosses: number[] }>();
  for (const n of nodes) {
    const px = isHoriz ? n.y : n.x;
    const py = isHoriz ? n.x : n.y;
    const mainPos = isHoriz ? px : py;
    const crossPos = isHoriz ? py : px;
    const entry = byDepth.get(n.depth) ?? { mainPos, crosses: [] };
    entry.crosses.push(crossPos);
    byDepth.set(n.depth, entry);
  }

  const waypoints: Waypoint[] = [];

  for (let d = 0; d <= maxDepth; d++) {
    const entry = byDepth.get(d);
    if (!entry) continue;

    const sorted = [...entry.crosses].sort((a, b) => a - b);
    const crossMin = sorted[0] - cellHalf;
    const crossMax = sorted[sorted.length - 1] + cellHalf;
    const crossSpan = crossMax - crossMin;

    const stops: number[] = [];
    if (crossSpan <= viewCross * 0.85) {
      stops.push((crossMin + crossMax) / 2);
    } else {
      const margin = viewCross / 2;
      const sweepFrom = crossMin + margin;
      const sweepTo = crossMax - margin;
      const chunkSize = viewCross * 0.75;
      const numStops = Math.max(2, Math.ceil((sweepTo - sweepFrom) / chunkSize) + 1);
      for (let s = 0; s < numStops; s++) {
        const t = numStops === 1 ? 0.5 : s / (numStops - 1);
        stops.push(sweepFrom + (sweepTo - sweepFrom) * t);
      }
    }

    for (let s = 0; s < stops.length; s++) {
      const crossTarget = stops[s];
      const cx = isHoriz ? entry.mainPos : crossTarget;
      const cy = isHoriz ? crossTarget : entry.mainPos;
      const isLastStop = s === stops.length - 1;
      const isLastLevel = d === maxDepth;
      let transitionAfter: number;
      if (isLastStop && isLastLevel) {
        transitionAfter = 0;
      } else if (isLastStop) {
        transitionAfter = LEVEL_TRANSITION;
      } else {
        transitionAfter = STOP_TRANSITION;
      }
      waypoints.push({ cx, cy, holdFrames: STOP_HOLD, transitionAfter, depth: d });
    }
  }

  return waypoints;
}

/** Total duration from a waypoint list. */
export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) {
    total += wp.holdFrames + wp.transitionAfter;
  }
  return Math.max(1, total);
}

/** Run d3 tree layout and return flat nodes + layout params. */
export function computeTreeLayout(
  input: HierarchySceneInput,
  isHoriz: boolean,
  vmin: number,
) {
  const rootData = normalizeToSingleRoot(input.items);
  const root = hierarchy(rootData, (d) => d.children ?? undefined);

  const dims = getMaxNodeSize(rootData, vmin);
  const siblingGap = vmin * 2;
  const levelGap = vmin * 10;
  const crossSize = (isHoriz ? dims.maxH : dims.maxW) + siblingGap;
  const mainSize = (isHoriz ? dims.maxW : dims.maxH) + levelGap;
  const treeLayout = tree<HierarchyNode>()
    .nodeSize([crossSize, mainSize])
    .separation(() => 1.2);
  treeLayout(root);

  const nodes = flattenNodes(root);
  return { nodes, crossSize, maxDepth: root.height };
}

/** Compute total scene duration for a hierarchy input. */
export function hierarchySceneDuration(
  input: HierarchySceneInput,
  viewW: number,
  viewH: number,
  isHoriz: boolean,
): number {
  const vmin = Math.min(viewW, viewH) / 100;
  const { nodes, crossSize, maxDepth } = computeTreeLayout(input, isHoriz, vmin);
  const wps = buildWaypoints(nodes, isHoriz, crossSize, viewW, viewH, maxDepth);
  return waypointsDuration(wps);
}
