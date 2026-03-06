/** Single tree node — card with style determined by variant.cardStyle. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { HierarchyNode } from "../types";
import type { HierarchyVariant, HierarchyCardStyle } from "../variant";
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

function cardCSS(
  style: HierarchyCardStyle,
  color: string,
  vmin: number,
  borderRadius: number,
  isRoot: boolean,
): React.CSSProperties {
  const bw = vmin * 0.14;

  switch (style) {
    case "gradient":
      return {
        background: `linear-gradient(145deg, ${color}14, ${color}06)`,
        border: `${bw}px solid ${color}35`,
        borderBottom: isRoot ? `${vmin * 0.35}px solid ${color}` : `${bw}px solid ${color}35`,
        boxShadow: `0 ${vmin * 0.5}px ${vmin * 2.5}px ${color}12`,
      };
    case "glass":
      return {
        background: `${color}0a`,
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: `${bw}px solid ${color}25`,
        boxShadow: `inset 0 0 ${vmin * 2}px ${color}08, 0 ${vmin * 0.5}px ${vmin * 2}px rgba(0,0,0,0.15)`,
      };
    case "outline":
      return {
        background: "transparent",
        border: `${vmin * 0.2}px solid ${color}${isRoot ? "bb" : "66"}`,
        boxShadow: `0 0 ${vmin * 1.5}px ${color}15`,
      };
    case "solid":
      return {
        background: `${color}22`,
        border: `${bw}px solid ${color}44`,
        boxShadow: `0 ${vmin * 0.3}px ${vmin * 1.5}px rgba(0,0,0,0.2)`,
      };
  }
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
  const styleCSS = cardCSS(variant.cardStyle, color, vmin, borderRadius, isRoot);

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        width: dims.width,
        minHeight: dims.height,
        boxSizing: "border-box" as const,
        position: "relative" as const,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: vmin * 0.4,
        padding: `${dims.paddingY}px ${dims.paddingX}px`,
        borderRadius,
        textAlign: "center" as const,
        ...styleCSS,
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
