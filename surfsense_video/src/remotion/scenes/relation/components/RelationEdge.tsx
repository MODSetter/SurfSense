/** SVG edge between two relation nodes with animated draw-in. */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { RelationEdgeStyle, RelationEdgeColorMode } from "../variant";
import { EDGE_DRAW_DURATION } from "../constants";

interface RelationEdgeProps {
  from: { x: number; y: number };
  to: { x: number; y: number };
  fromColor: string;
  toColor: string;
  label?: string;
  enterFrame: number;
  vmin: number;
  theme: ThemeColors;
  edgeStyle: RelationEdgeStyle;
  edgeColorMode: RelationEdgeColorMode;
  showArrow: boolean;
  showLabel: boolean;
  edgeId: string;
}

export const RelationEdge: React.FC<RelationEdgeProps> = ({
  from,
  to,
  fromColor,
  toColor,
  label,
  enterFrame,
  vmin,
  theme,
  edgeStyle,
  edgeColorMode,
  showArrow,
  showLabel,
  edgeId,
}) => {
  const frame = useCurrentFrame();
  const localFrame = frame - enterFrame;

  const progress = interpolate(
    localFrame,
    [0, EDGE_DRAW_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const opacity = interpolate(
    localFrame,
    [0, EDGE_DRAW_DURATION * 0.5],
    [0, 0.7],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  if (progress <= 0) return null;

  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2;

  const strokeW = vmin * 0.12;
  const gradId = `edge-grad-${edgeId}`;
  const strokeColor =
    edgeColorMode === "gradient" ? `url(#${gradId})` : `${fromColor}50`;

  const headSize = vmin * 0.7;
  const angle = Math.atan2(to.y - from.y, to.x - from.x);

  const pad = vmin * 2;
  const minX = Math.min(from.x, to.x) - pad;
  const minY = Math.min(from.y, to.y) - pad;
  const maxX = Math.max(from.x, to.x) + pad;
  const maxY = Math.max(from.y, to.y) + pad;
  const svgW = maxX - minX;
  const svgH = maxY - minY;

  return (
    <svg
      style={{
        position: "absolute",
        left: minX,
        top: minY,
        width: svgW,
        height: svgH,
        overflow: "visible",
        pointerEvents: "none",
      }}
      viewBox={`${minX} ${minY} ${svgW} ${svgH}`}
    >
      <defs>
        {edgeColorMode === "gradient" && (
          <linearGradient
            id={gradId}
            gradientUnits="userSpaceOnUse"
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
          >
            <stop offset="0%" stopColor={fromColor} stopOpacity={0.4} />
            <stop offset="100%" stopColor={toColor} stopOpacity={0.4} />
          </linearGradient>
        )}
      </defs>

      <line
        x1={from.x}
        y1={from.y}
        x2={from.x + (to.x - from.x) * progress}
        y2={from.y + (to.y - from.y) * progress}
        stroke={strokeColor}
        strokeWidth={strokeW}
        strokeDasharray={edgeStyle === "dashed" ? `${vmin * 0.5},${vmin * 0.35}` : "none"}
        opacity={opacity}
      />

      {showArrow && progress > 0.9 && (
        <polygon
          points={`
            ${to.x},${to.y}
            ${to.x - headSize * Math.cos(angle - 0.35)},${to.y - headSize * Math.sin(angle - 0.35)}
            ${to.x - headSize * Math.cos(angle + 0.35)},${to.y - headSize * Math.sin(angle + 0.35)}
          `}
          fill={edgeColorMode === "gradient" ? `${toColor}60` : `${fromColor}50`}
          opacity={opacity}
        />
      )}

      {showLabel && label && progress > 0.6 && (
        <text
          x={mx}
          y={my - vmin * 0.6}
          textAnchor="middle"
          dominantBaseline="auto"
          fill={`${theme.textSecondary}90`}
          fontSize={vmin * 1}
          fontFamily="Inter, system-ui, sans-serif"
          opacity={opacity}
        >
          {label}
        </text>
      )}
    </svg>
  );
};
