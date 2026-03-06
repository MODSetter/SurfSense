/** Single list item — card with index badge, label, optional value + desc. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { ListItem as ListItemData } from "../types";
import type { ListVariant } from "../variant";
import { ITEM_FADE_DURATION } from "../constants";

interface ListItemProps {
  item: ListItemData;
  index: number;
  enterFrame: number;
  vmin: number;
  variant: ListVariant;
  theme: ThemeColors;
  cardWidth: number;
  cardHeight: number;
}

export const ListItemCard: React.FC<ListItemProps> = ({
  item,
  index,
  enterFrame,
  vmin,
  variant,
  theme,
  cardWidth,
  cardHeight,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const color = item.color ?? "#6c7dff";
  const localFrame = frame - enterFrame;

  const opacity = interpolate(localFrame, [0, ITEM_FADE_DURATION], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const scale = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.8 },
  });

  const borderRadius = variant.itemShape === "pill" ? 999 : vmin * 1.2;
  const paddingX = vmin * 2;
  const paddingY = vmin * 1.5;

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        width: cardWidth,
        height: cardHeight,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: vmin * 1.5,
        padding: `${paddingY}px ${paddingX}px`,
        borderRadius,
        background: `${color}18`,
        border: `${vmin * 0.14}px solid ${color}55`,
        boxShadow: `0 0 ${vmin * 2}px ${color}20`,
        overflow: "hidden",
      }}
    >
      {(variant.showIndex || item.value !== undefined) && (
        <div
          style={{
            flexShrink: 0,
            width: vmin * 5,
            height: vmin * 5,
            borderRadius: "50%",
            background: `${color}30`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: color,
            fontSize: item.value !== undefined ? vmin * 2 : vmin * 1.8,
            fontWeight: 700,
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        >
          {item.value !== undefined ? item.value : String(index + 1).padStart(2, "0")}
        </div>
      )}

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: vmin * 0.3,
          minWidth: 0,
        }}
      >
        <span
          style={{
            color: theme.textPrimary,
            fontSize: vmin * 1.8,
            fontWeight: 600,
            fontFamily: "Inter, system-ui, sans-serif",
            lineHeight: 1.3,
          }}
        >
          {item.label}
        </span>
        {item.desc && (
          <span
            style={{
              color: theme.textSecondary,
              fontSize: vmin * 1.2,
              fontFamily: "Inter, system-ui, sans-serif",
              lineHeight: 1.4,
            }}
          >
            {item.desc}
          </span>
        )}
      </div>
    </div>
  );
};
