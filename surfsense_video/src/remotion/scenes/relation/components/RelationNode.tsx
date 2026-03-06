/** Single relation node card with variant-driven styling. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { RelationNode as RelationNodeData } from "../types";
import type { RelationCardStyle } from "../variant";
import { NODE_FADE_DURATION } from "../constants";
import { getNodeDimensions } from "./nodeSize";

interface RelationNodeProps {
  node: RelationNodeData;
  enterFrame: number;
  vmin: number;
  cardStyle: RelationCardStyle;
  theme: ThemeColors;
}

function cardCSS(
  style: RelationCardStyle,
  color: string,
  vmin: number,
): React.CSSProperties {
  const bw = vmin * 0.14;

  switch (style) {
    case "gradient":
      return {
        background: `linear-gradient(145deg, ${color}14, ${color}06)`,
        border: `${bw}px solid ${color}35`,
        boxShadow: `0 ${vmin * 0.5}px ${vmin * 2}px ${color}12`,
      };
    case "glass":
      return {
        background: `${color}0a`,
        backdropFilter: "blur(12px)",
        border: `${bw}px solid ${color}20`,
        boxShadow: `inset 0 ${vmin * 0.1}px ${vmin * 0.6}px ${color}15`,
      };
    case "outline":
      return {
        background: "transparent",
        border: `${vmin * 0.2}px solid ${color}60`,
      };
    case "solid":
      return {
        background: `${color}18`,
        border: `${bw}px solid ${color}30`,
      };
  }
}

export const RelationNodeComponent: React.FC<RelationNodeProps> = ({
  node,
  enterFrame,
  vmin,
  cardStyle,
  theme,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - enterFrame;

  const opacity = interpolate(
    localFrame,
    [0, NODE_FADE_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const scale = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.5 },
  });

  const color = node.color ?? "#6c7dff";
  const dims = getNodeDimensions(node, vmin);
  const borderRadius = vmin * 1;

  return (
    <div
      style={{
        width: dims.width,
        height: dims.height,
        borderRadius,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: `${dims.paddingY}px ${dims.paddingX}px`,
        boxSizing: "border-box",
        opacity,
        transform: `scale(${scale})`,
        ...cardCSS(cardStyle, color, vmin),
      }}
    >
      <div
        style={{
          color: theme.textPrimary,
          fontSize: dims.fontSize,
          fontWeight: 600,
          fontFamily: "Inter, system-ui, sans-serif",
          lineHeight: 1.3,
          textAlign: "center",
        }}
      >
        {node.label}
      </div>
      {node.desc && (
        <div
          style={{
            color: theme.textSecondary,
            fontSize: dims.descFontSize,
            fontWeight: 400,
            fontFamily: "Inter, system-ui, sans-serif",
            lineHeight: 1.3,
            marginTop: vmin * 0.4,
            textAlign: "center",
          }}
        >
          {node.desc}
        </div>
      )}
    </div>
  );
};
