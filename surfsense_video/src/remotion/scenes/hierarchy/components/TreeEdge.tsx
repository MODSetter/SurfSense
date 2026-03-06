/** Animated edge between parent and child node in the tree. */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { HierarchyVariant } from "../variant";
import { EDGE_DRAW_DURATION } from "../constants";

interface Point {
  x: number;
  y: number;
}

interface TreeEdgeProps {
  from: Point;
  to: Point;
  parentColor: string;
  childColor: string;
  enterFrame: number;
  variant: HierarchyVariant;
  edgeId: string;
}

function buildCurvedPath(from: Point, to: Point, isHorizontal: boolean): string {
  if (isHorizontal) {
    const mx = from.x + (to.x - from.x) / 2;
    return `M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`;
  }
  const my = from.y + (to.y - from.y) / 2;
  return `M ${from.x} ${from.y} C ${from.x} ${my}, ${to.x} ${my}, ${to.x} ${to.y}`;
}

function buildStraightPath(
  from: Point,
  to: Point,
  isHorizontal: boolean,
  radius: number,
): string {
  if (radius <= 0) {
    if (isHorizontal) {
      const mx = from.x + (to.x - from.x) / 2;
      return `M ${from.x} ${from.y} L ${mx} ${from.y} L ${mx} ${to.y} L ${to.x} ${to.y}`;
    }
    const my = from.y + (to.y - from.y) / 2;
    return `M ${from.x} ${from.y} L ${from.x} ${my} L ${to.x} ${my} L ${to.x} ${to.y}`;
  }

  const isVert = !isHorizontal;
  const deltaMain = isVert ? to.y - from.y : to.x - from.x;
  const deltaCross = isVert ? to.x - from.x : to.y - from.y;
  const signM = Math.sign(deltaMain) || 1;
  const signC = Math.sign(deltaCross) || 1;
  const mid = isVert
    ? from.y + deltaMain / 2
    : from.x + deltaMain / 2;
  const r = Math.min(radius, Math.abs(deltaMain) / 2, Math.abs(deltaCross) / 2);

  if (r === 0) {
    return buildStraightPath(from, to, isHorizontal, 0);
  }

  if (isVert) {
    return [
      `M ${from.x} ${from.y}`,
      `L ${from.x} ${mid - signM * r}`,
      `Q ${from.x} ${mid} ${from.x + signC * r} ${mid}`,
      `L ${to.x - signC * r} ${mid}`,
      `Q ${to.x} ${mid} ${to.x} ${mid + signM * r}`,
      `L ${to.x} ${to.y}`,
    ].join(" ");
  }
  return [
    `M ${from.x} ${from.y}`,
    `L ${mid - signM * r} ${from.y}`,
    `Q ${mid} ${from.y} ${mid} ${from.y + signC * r}`,
    `L ${mid} ${to.y - signC * r}`,
    `Q ${mid} ${to.y} ${mid + signM * r} ${to.y}`,
    `L ${to.x} ${to.y}`,
  ].join(" ");
}

export const TreeEdge: React.FC<TreeEdgeProps> = ({
  from,
  to,
  parentColor,
  childColor,
  enterFrame,
  variant,
  edgeId,
}) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;
  const isHoriz = variant.orientation === "left-right";

  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const pathLen = Math.sqrt(dx * dx + dy * dy) * 1.5;

  const d =
    variant.edgeType === "curved"
      ? buildCurvedPath(from, to, isHoriz)
      : buildStraightPath(from, to, isHoriz, variant.edgeCornerRadius * vmin);

  const localFrame = frame - enterFrame;

  const progress = interpolate(
    localFrame,
    [0, EDGE_DRAW_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const fadeIn = interpolate(localFrame, [0, 5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const isDrawn = localFrame > EDGE_DRAW_DURATION;
  const breathCycle = isDrawn
    ? Math.sin(((localFrame - EDGE_DRAW_DURATION) / fps) * 1.8) * 0.15
    : 0;
  const opacity = fadeIn * (1 + breathCycle);
  const strokeW = vmin * 0.25 * (1 + breathCycle * 0.5);

  const useGradient = variant.edgeColorMode === "gradient";
  const gradientId = `edge-grad-${edgeId}`;

  const minX = Math.min(from.x, to.x) - 10;
  const minY = Math.min(from.y, to.y) - 10;
  const svgW = Math.abs(to.x - from.x) + 20;
  const svgH = Math.abs(to.y - from.y) + 20;

  return (
    <svg
      viewBox={`${minX} ${minY} ${svgW} ${svgH}`}
      style={{
        position: "absolute",
        left: minX,
        top: minY,
        width: svgW,
        height: svgH,
        pointerEvents: "none",
        overflow: "visible",
      }}
    >
      {useGradient && (
        <defs>
          <linearGradient
            id={gradientId}
            gradientUnits="userSpaceOnUse"
            x1={from.x} y1={from.y}
            x2={to.x} y2={to.y}
          >
            <stop offset="0%" stopColor={parentColor} />
            <stop offset="100%" stopColor={childColor} />
          </linearGradient>
        </defs>
      )}
      <path
        d={d}
        fill="none"
        stroke={useGradient ? `url(#${gradientId})` : parentColor}
        strokeWidth={strokeW}
        strokeDasharray={pathLen}
        strokeDashoffset={pathLen * (1 - progress)}
        opacity={opacity}
      />
    </svg>
  );
};
