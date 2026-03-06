/**
 * Relation scene layout — circle, network (force), dagre (layered).
 * Computes node positions, camera waypoints, and scene duration.
 */
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import type { RelationSceneInput, LayoutNode, Waypoint } from "./types";
import type { RelationLayout } from "./variant";
import { getMaxNodeSize, getNodeDimensions } from "./components/nodeSize";
import {
  NODE_STAGGER,
  NODE_FADE_DURATION,
  STOP_HOLD,
  STOP_TRANSITION,
} from "./constants";

/* ─── Circle layout ─── */

function layoutCircle(
  input: RelationSceneInput,
  vmin: number,
): LayoutNode[] {
  const { maxW, maxH } = getMaxNodeSize(input.nodes, vmin);
  const size = Math.max(maxW, maxH);
  const count = input.nodes.length;

  if (count === 1) {
    return [{ data: input.nodes[0], x: 0, y: 0, index: 0 }];
  }

  const minGap = vmin * 8;
  const radius = Math.max(
    size * 2,
    (count * (size + minGap)) / (2 * Math.PI),
  );

  return input.nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    return {
      data: node,
      x: radius * Math.cos(angle),
      y: radius * Math.sin(angle),
      index: i,
    };
  });
}

/* ─── Network (force) layout ─── */

interface ForceNode extends SimulationNodeDatum {
  id: string;
  _index: number;
}

function layoutNetwork(
  input: RelationSceneInput,
  vmin: number,
): LayoutNode[] {
  const { maxW, maxH } = getMaxNodeSize(input.nodes, vmin);
  const nodeSize = Math.max(maxW, maxH);
  const spacing = nodeSize + vmin * 10;
  const idSet = new Set(input.nodes.map((n) => n.id));

  const forceNodes: ForceNode[] = input.nodes.map((n, i) => ({
    id: n.id,
    _index: i,
  }));

  const forceLinks: SimulationLinkDatum<ForceNode>[] = input.edges
    .filter((e) => idSet.has(e.from) && idSet.has(e.to))
    .map((e) => ({ source: e.from, target: e.to }));

  const sim = forceSimulation(forceNodes)
    .force(
      "link",
      forceLink<ForceNode, SimulationLinkDatum<ForceNode>>(forceLinks)
        .id((d) => d.id)
        .distance(spacing)
        .strength(0.6),
    )
    .force("charge", forceManyBody().strength(-spacing * 1.5))
    .force("center", forceCenter(0, 0))
    .force("collision", forceCollide(nodeSize / 2 + vmin * 4));

  for (let i = 0; i < 300; i++) sim.tick();
  sim.stop();

  return forceNodes.map((fn) => ({
    data: input.nodes[fn._index],
    x: fn.x ?? 0,
    y: fn.y ?? 0,
    index: fn._index,
  }));
}

/* ─── Dagre (simplified layered) layout ─── */

function layoutDagre(
  input: RelationSceneInput,
  vmin: number,
  isHoriz: boolean,
): LayoutNode[] {
  const idToIdx = new Map(input.nodes.map((n, i) => [n.id, i]));
  const n = input.nodes.length;

  const adj = new Map<number, number[]>();
  const inDeg = new Array(n).fill(0);
  for (let i = 0; i < n; i++) adj.set(i, []);

  for (const e of input.edges) {
    const si = idToIdx.get(e.from);
    const ti = idToIdx.get(e.to);
    if (si != null && ti != null && si !== ti) {
      adj.get(si)!.push(ti);
      inDeg[ti]++;
    }
  }

  const rank = new Array(n).fill(0);
  const queue: number[] = [];
  for (let i = 0; i < n; i++) {
    if (inDeg[i] === 0) queue.push(i);
  }
  if (queue.length === 0) queue.push(0);

  const visited = new Set<number>();
  while (queue.length > 0) {
    const cur = queue.shift()!;
    if (visited.has(cur)) continue;
    visited.add(cur);
    for (const next of adj.get(cur) ?? []) {
      rank[next] = Math.max(rank[next], rank[cur] + 1);
      if (!visited.has(next)) queue.push(next);
    }
  }
  for (let i = 0; i < n; i++) {
    if (!visited.has(i)) {
      visited.add(i);
      rank[i] = 0;
    }
  }

  const byRank = new Map<number, number[]>();
  for (let i = 0; i < n; i++) {
    const r = rank[i];
    if (!byRank.has(r)) byRank.set(r, []);
    byRank.get(r)!.push(i);
  }

  const dims = input.nodes.map((nd) => getNodeDimensions(nd, vmin));
  const gapCross = vmin * 8;
  const gapBetweenRanks = vmin * 10;

  const maxMainSize = Math.max(
    ...dims.map((d) => (isHoriz ? d.width : d.height)),
  );
  const rankStep = maxMainSize + gapBetweenRanks;

  const nodes: LayoutNode[] = [];

  const rankEntries = Array.from(byRank.entries());
  for (const [r, indices] of rankEntries) {
    const totalCross = indices.reduce(
      (sum: number, i: number) => sum + (isHoriz ? dims[i].height : dims[i].width) + gapCross,
      -gapCross,
    );
    let cursor = -totalCross / 2;

    for (const i of indices) {
      const d = dims[i];
      const crossSize = isHoriz ? d.height : d.width;
      const crossPos = cursor + crossSize / 2;
      cursor += crossSize + gapCross;

      const mainPos = r * rankStep;
      nodes.push({
        data: input.nodes[i],
        x: isHoriz ? mainPos : crossPos,
        y: isHoriz ? crossPos : mainPos,
        index: i,
      });
    }
  }

  return nodes;
}

/* ─── Camera waypoints ─── */

export function buildWaypoints(
  nodes: LayoutNode[],
  nodeW: number,
  nodeH: number,
  viewW: number,
  viewH: number,
  titleOffset: number = 0,
): Waypoint[] {
  if (nodes.length === 0) {
    return [{ cx: 0, cy: -titleOffset / 2, holdFrames: STOP_HOLD, transitionAfter: 0 }];
  }

  const pad = Math.max(nodeW, nodeH) * 0.6;
  const minX = Math.min(...nodes.map((n) => n.x)) - pad;
  const maxX = Math.max(...nodes.map((n) => n.x)) + pad;
  const minY = Math.min(...nodes.map((n) => n.y)) - pad;
  const maxY = Math.max(...nodes.map((n) => n.y)) + pad;

  const spanW = maxX - minX;
  const spanH = maxY - minY;
  const contentCX = (minX + maxX) / 2;
  const contentCY = (minY + maxY) / 2;
  const effectiveH = viewH - titleOffset;

  const centeredCY = contentCY - titleOffset / 2;

  if (spanW <= viewW * 0.85 && spanH <= effectiveH * 0.85) {
    return [{ cx: contentCX, cy: centeredCY, holdFrames: STOP_HOLD, transitionAfter: 0 }];
  }

  const colsNeeded = spanW > viewW ? Math.ceil(spanW / (viewW * 0.75)) : 1;
  const rowsNeeded = spanH > effectiveH ? Math.ceil(spanH / (effectiveH * 0.75)) : 1;

  const stops: Waypoint[] = [];

  for (let r = 0; r < rowsNeeded; r++) {
    for (let c = 0; c < colsNeeded; c++) {
      const tx = colsNeeded === 1
        ? contentCX
        : minX + viewW / 2 + (c / (colsNeeded - 1)) * (spanW - viewW);

      let ty: number;
      if (rowsNeeded === 1) {
        ty = centeredCY;
      } else {
        const firstCy = minY + viewH / 2 - titleOffset;
        const lastCy = maxY - viewH / 2;
        ty = firstCy + (r / (rowsNeeded - 1)) * (lastCy - firstCy);
      }

      stops.push({
        cx: tx,
        cy: ty,
        holdFrames: STOP_HOLD,
        transitionAfter: STOP_TRANSITION,
      });
    }
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

/* ─── Public API ─── */

export function computeRelationLayout(
  input: RelationSceneInput,
  layout: RelationLayout,
  vmin: number,
): LayoutNode[] {
  switch (layout) {
    case "circle":
      return layoutCircle(input, vmin);
    case "network":
      return layoutNetwork(input, vmin);
    case "dagre-tb":
      return layoutDagre(input, vmin, false);
    case "dagre-lr":
      return layoutDagre(input, vmin, true);
  }
}

export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) total += wp.holdFrames + wp.transitionAfter;
  return Math.max(1, total);
}

export function relationSceneDuration(
  input: RelationSceneInput,
  layout: RelationLayout,
  viewW: number,
  viewH: number,
): number {
  const vmin = Math.min(viewW, viewH) / 100;
  const titleOffset = input.title ? vmin * 12 : 0;
  const nodes = computeRelationLayout(input, layout, vmin);
  const { maxW, maxH } = getMaxNodeSize(input.nodes, vmin);
  const wps = buildWaypoints(nodes, maxW, maxH, viewW, viewH, titleOffset);
  const animPhase = (input.nodes.length - 1) * NODE_STAGGER + NODE_FADE_DURATION;
  return animPhase + waypointsDuration(wps);
}
