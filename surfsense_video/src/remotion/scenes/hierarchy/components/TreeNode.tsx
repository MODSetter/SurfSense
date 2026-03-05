/** Single tree node — rounded card with label, optional desc. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { HierarchyNode } from "../types";
import type { HierarchyVariant } from "../variant";
import { NODE_FADE_DURATION } from "../constants";
import { getNodeDimensions } from "./nodeSize";

interface TreeNodeProps {
  node: HierarchyNode;
  enterFrame: number;
  depth: number;
  vmin: number;
  variant: HierarchyVariant;
  theme: ThemeColors;
  isRoot: boolean;
}

export const TreeNode: React.FC<TreeNodeProps> = ({
  node,
  enterFrame,
  vmin,
  variant,
  theme,
  isRoot,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const color = node.color ?? "#6c7dff";
  const localFrame = frame - enterFrame;
  const dims = getNodeDimensions(node, vmin, isRoot);

  const opacity = interpolate(localFrame, [0, NODE_FADE_DURATION], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const scale = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.8 },
  });

  const borderRadius = variant.nodeShape === "pill" ? 999 : vmin * 1;

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        width: dims.width,
        minHeight: dims.height,
        boxSizing: "border-box" as const,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: vmin * 0.4,
        padding: `${dims.paddingY}px ${dims.paddingX}px`,
        borderRadius,
        background: `${color}18`,
        border: `${vmin * 0.14}px solid ${color}55`,
        boxShadow: `0 0 ${vmin * 2}px ${color}20`,
        textAlign: "center" as const,
      }}
    >
      <span
        style={{
          color: theme.textPrimary,
          fontSize: dims.fontSize,
          fontWeight: isRoot ? 700 : 500,
          fontFamily: "Inter, system-ui, sans-serif",
          lineHeight: 1.3,
        }}
      >
        {node.label}
      </span>
      {node.desc && (
        <span
          style={{
            color: theme.textSecondary,
            fontSize: dims.descFontSize,
            fontFamily: "Inter, system-ui, sans-serif",
            lineHeight: 1.3,
          }}
        >
          {node.desc}
        </span>
      )}
    </div>
  );
};
