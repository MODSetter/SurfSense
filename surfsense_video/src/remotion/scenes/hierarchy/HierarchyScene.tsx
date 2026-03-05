/**
 * HierarchyScene — tree layout powered by d3-hierarchy.
 *
 * Nodes are placed via d3.tree(), then rendered with staggered
 * per-level reveal animations and animated edge drawing.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { HierarchySceneInput, LayoutNode, Waypoint } from "./types";
import type { HierarchyVariant } from "./variant";
import { NODE_STAGGER, EDGE_DRAW_DURATION } from "./constants";
import { TreeNode } from "./components/TreeNode";
import { TreeEdge } from "./components/TreeEdge";
import { getNodeDimensions } from "./components/nodeSize";
import { computeTreeLayout, buildWaypoints } from "./layout";

interface HierarchySceneProps {
  input: HierarchySceneInput;
  theme: ThemeColors;
  variant: HierarchyVariant;
}

/** Resolve camera position from waypoints at a given frame. */
function resolveCamera(waypoints: Waypoint[], frame: number): { cx: number; cy: number } {
  let cam = { cx: waypoints[0].cx, cy: waypoints[0].cy };
  let cursor = 0;

  for (let w = 0; w < waypoints.length; w++) {
    const wp = waypoints[w];
    if (frame < cursor + wp.holdFrames) {
      cam = { cx: wp.cx, cy: wp.cy };
      break;
    }
    cursor += wp.holdFrames;

    if (wp.transitionAfter > 0 && w + 1 < waypoints.length) {
      if (frame < cursor + wp.transitionAfter) {
        const t = Easing.inOut(Easing.ease)(
          (frame - cursor) / wp.transitionAfter,
        );
        const next = waypoints[w + 1];
        cam = {
          cx: wp.cx + (next.cx - wp.cx) * t,
          cy: wp.cy + (next.cy - wp.cy) * t,
        };
        break;
      }
      cursor += wp.transitionAfter;
    }

    if (w === waypoints.length - 1) {
      cam = { cx: wp.cx, cy: wp.cy };
    }
  }

  return cam;
}

/** Build a map from depth → frame at which that depth's first waypoint starts. */
function buildDepthEnterFrames(waypoints: Waypoint[]): Map<number, number> {
  const map = new Map<number, number>();
  let f = 0;
  for (const wp of waypoints) {
    if (!map.has(wp.depth)) map.set(wp.depth, f);
    f += wp.holdFrames + wp.transitionAfter;
  }
  return map;
}

export const HierarchyScene: React.FC<HierarchySceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const { width, height } = useVideoConfig();
  const isHoriz = variant.orientation === "left-right";
  const vmin = Math.min(width, height) / 100;
  const frame = useCurrentFrame();

  const { nodes, waypoints, depthEnterFrame } = useMemo(() => {
    const { nodes: flat, crossSize, maxDepth } = computeTreeLayout(input, isHoriz, vmin);
    const wps = buildWaypoints(flat, isHoriz, crossSize, width, height, maxDepth);
    const def = buildDepthEnterFrames(wps);
    return { nodes: flat, waypoints: wps, depthEnterFrame: def };
  }, [input, isHoriz, vmin, width, height]);

  const cam = resolveCamera(waypoints, frame);
  const panX = -cam.cx;
  const panY = -cam.cy;

  const toLocal = (n: LayoutNode) => {
    const px = isHoriz ? n.y : n.x;
    const py = isHoriz ? n.x : n.y;
    return { lx: px, ly: py };
  };

  const edges: {
    from: { x: number; y: number };
    to: { x: number; y: number };
    parentColor: string;
    childColor: string;
    enterFrame: number;
    id: string;
  }[] = [];

  let edgeIdx = 0;
  for (const n of nodes) {
    if (!n.parent) continue;
    const pLocal = toLocal(n.parent);
    const cLocal = toLocal(n);
    const pDims = getNodeDimensions(n.parent.data, vmin, n.parent.depth === 0);
    const cDims = getNodeDimensions(n.data, vmin, n.depth === 0);

    const from = { x: pLocal.lx, y: pLocal.ly };
    const to = { x: cLocal.lx, y: cLocal.ly };

    if (isHoriz) {
      from.x += pDims.halfW;
      to.x -= cDims.halfW;
    } else {
      from.y += pDims.halfH;
      to.y -= cDims.halfH;
    }

    const levelStart = depthEnterFrame.get(n.depth) ?? 0;
    const enterF = levelStart - EDGE_DRAW_DURATION + n.siblingIndex * 4;
    edges.push({
      from,
      to,
      parentColor: n.parent.data.color ?? "#6c7dff",
      childColor: n.data.color ?? "#6c7dff",
      enterFrame: Math.max(0, enterF),
      id: `e${edgeIdx++}`,
    });
  }

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: width / 2 + panX,
          top: height / 2 + panY,
        }}
      >
        {edges.map((e) => (
          <TreeEdge
            key={e.id}
            from={e.from}
            to={e.to}
            parentColor={e.parentColor}
            childColor={e.childColor}
            enterFrame={e.enterFrame}
            variant={variant}
            edgeId={e.id}
          />
        ))}

        {nodes.map((n, i) => {
          const { lx, ly } = toLocal(n);
          const levelStart = depthEnterFrame.get(n.depth) ?? 0;
          const enterF = levelStart + n.siblingIndex * NODE_STAGGER;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: lx,
                top: ly,
                transform: "translate(-50%, -50%)",
              }}
            >
              <TreeNode
                node={n.data}
                enterFrame={enterF}
                depth={n.depth}
                vmin={vmin}
                variant={variant}
                theme={theme}
                isRoot={n.depth === 0}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
