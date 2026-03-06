/**
 * RelationScene — renders nodes + edges in circle, network, or dagre layout
 * with staggered reveals, animated edge drawing, and camera paging.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { RelationSceneInput, Waypoint } from "./types";
import type { RelationVariant } from "./variant";
import { NODE_STAGGER } from "./constants";
import { RelationNodeComponent } from "./components/RelationNode";
import { RelationEdge } from "./components/RelationEdge";
import { getNodeDimensions, getMaxNodeSize } from "./components/nodeSize";
import { computeRelationLayout, buildWaypoints } from "./layout";

/** Find the point on a rectangle's border closest to a target direction. */
function rectEdgePoint(
  cx: number, cy: number,
  halfW: number, halfH: number,
  tx: number, ty: number,
): { x: number; y: number } {
  const dx = tx - cx;
  const dy = ty - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy - halfH };

  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);
  const slopeRatio = halfH / halfW;

  if (absDy / (absDx || 1) <= slopeRatio) {
    const sx = dx > 0 ? 1 : -1;
    return { x: cx + sx * halfW, y: cy + (dy / absDx) * halfW };
  }
  const sy = dy > 0 ? 1 : -1;
  return { x: cx + (dx / absDy) * halfH, y: cy + sy * halfH };
}

interface RelationSceneProps {
  input: RelationSceneInput;
  theme: ThemeColors;
  variant: RelationVariant;
}

function resolveCamera(
  waypoints: Waypoint[],
  frame: number,
): { cx: number; cy: number } {
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

export const RelationScene: React.FC<RelationSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const { width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;
  const frame = useCurrentFrame();

  const titleOffset = input.title ? vmin * 12 : 0;

  const { nodes, waypoints, idToNode } = useMemo(() => {
    const laid = computeRelationLayout(input, variant.layout, vmin);
    const { maxW, maxH } = getMaxNodeSize(input.nodes, vmin);
    const wps = buildWaypoints(laid, maxW, maxH, width, height, titleOffset);

    const idMap = new Map<string, (typeof laid)[number]>();
    for (const n of laid) idMap.set(n.data.id, n);

    return { nodes: laid, waypoints: wps, idToNode: idMap };
  }, [input, variant.layout, vmin, width, height, titleOffset]);

  const cam = resolveCamera(waypoints, frame);
  const panX = -cam.cx;
  const panY = -cam.cy;

  interface ResolvedEdge {
    from: { x: number; y: number };
    to: { x: number; y: number };
    fromColor: string;
    toColor: string;
    label?: string;
    enterFrame: number;
    id: string;
  }

  const resolvedEdges = useMemo<ResolvedEdge[]>(() => {
    const result: ResolvedEdge[] = [];
    input.edges.forEach((e, i) => {
      const src = idToNode.get(e.from);
      const tgt = idToNode.get(e.to);
      if (!src || !tgt) return;

      const srcDims = getNodeDimensions(src.data, vmin);
      const tgtDims = getNodeDimensions(tgt.data, vmin);

      result.push({
        from: rectEdgePoint(src.x, src.y, srcDims.halfW, srcDims.halfH, tgt.x, tgt.y),
        to: rectEdgePoint(tgt.x, tgt.y, tgtDims.halfW, tgtDims.halfH, src.x, src.y),
        fromColor: src.data.color ?? "#6c7dff",
        toColor: tgt.data.color ?? "#6c7dff",
        label: e.label,
        enterFrame: Math.max(0, Math.max(src.index, tgt.index) * NODE_STAGGER),
        id: `re${i}`,
      });
    });
    return result;
  }, [input.edges, idToNode, vmin]);

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      {input.title && (
        <div
          style={{
            position: "absolute",
            top: vmin * 3,
            left: 0,
            width: "100%",
            textAlign: "center",
            zIndex: 10,
          }}
        >
          <div
            style={{
              color: theme.textPrimary,
              fontSize: vmin * 3.5,
              fontWeight: 700,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {input.title}
          </div>
          {input.subtitle && (
            <div
              style={{
                color: theme.textSecondary,
                fontSize: vmin * 1.8,
                fontFamily: "Inter, system-ui, sans-serif",
                marginTop: vmin * 0.5,
              }}
            >
              {input.subtitle}
            </div>
          )}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          left: width / 2 + panX,
          top: height / 2 + panY,
        }}
      >
        {resolvedEdges.map((e) => (
          <RelationEdge
            key={e.id}
            from={e.from}
            to={e.to}
            fromColor={e.fromColor}
            toColor={e.toColor}
            label={e.label}
            enterFrame={e.enterFrame}
            vmin={vmin}
            theme={theme}
            edgeStyle={variant.edgeStyle}
            edgeColorMode={variant.edgeColorMode}
            showArrow={variant.showArrows}
            showLabel={variant.showEdgeLabels}
            edgeId={e.id}
          />
        ))}

        {nodes.map((n) => {
          const enterF = n.index * NODE_STAGGER;
          return (
            <div
              key={n.data.id}
              style={{
                position: "absolute",
                left: n.x,
                top: n.y,
                transform: "translate(-50%, -50%)",
              }}
            >
              <RelationNodeComponent
                node={n.data}
                enterFrame={enterF}
                vmin={vmin}
                cardStyle={variant.cardStyle}
                theme={theme}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
