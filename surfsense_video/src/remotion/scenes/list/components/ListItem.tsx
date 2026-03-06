/** Single list item — card with style determined by variant.cardStyle. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { ListItem as ListItemData } from "../types";
import type { ListVariant, ListCardStyle } from "../variant";
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

function listCardCSS(
  style: ListCardStyle,
  color: string,
  vmin: number,
): React.CSSProperties {
  const bw = vmin * 0.14;

  switch (style) {
    case "accent-left":
      return {
        background: `${color}0d`,
        border: `${bw}px solid ${color}20`,
        borderLeft: `${vmin * 0.45}px solid ${color}`,
        boxShadow: `${vmin * 0.2}px ${vmin * 0.4}px ${vmin * 1.8}px rgba(0,0,0,0.25)`,
      };
    case "accent-bottom":
      return {
        background: `linear-gradient(180deg, ${color}12, ${color}06)`,
        border: `${bw}px solid ${color}25`,
        borderBottom: `${vmin * 0.35}px solid ${color}`,
        boxShadow: `0 ${vmin * 0.5}px ${vmin * 2}px ${color}10`,
      };
    case "filled":
      return {
        background: `${color}22`,
        border: `${bw}px solid ${color}44`,
        boxShadow: `0 ${vmin * 0.3}px ${vmin * 1.5}px rgba(0,0,0,0.2)`,
      };
    case "minimal":
      return {
        background: `${color}08`,
        border: `${bw}px solid ${color}18`,
        boxShadow: "none",
      };
  }
}

function listBadgeCSS(
  style: ListCardStyle,
  color: string,
  vmin: number,
): React.CSSProperties {
  switch (style) {
    case "accent-left":
      return { background: color, color: "#fff" };
    case "accent-bottom":
      return { background: `${color}25`, color, border: `${vmin * 0.15}px solid ${color}55` };
    case "filled":
      return { background: `${color}44`, color: "#fff" };
    case "minimal":
      return { background: "transparent", color, border: `${vmin * 0.18}px solid ${color}` };
  }
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
  const styleCSS = listCardCSS(variant.cardStyle, color, vmin);
  const badgeCSS = listBadgeCSS(variant.cardStyle, color, vmin);

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        width: cardWidth,
        height: cardHeight,
        boxSizing: "border-box",
        position: "relative",
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        gap: vmin * 1.5,
        padding: `${paddingY}px ${paddingX}px`,
        borderRadius,
        overflow: "hidden",
        ...styleCSS,
      }}
    >
      {(variant.showIndex || item.value !== undefined) && (
        <div
          style={{
            flexShrink: 0,
            width: vmin * 5,
            height: vmin * 5,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: item.value !== undefined ? vmin * 2 : vmin * 1.8,
            fontWeight: 700,
            fontFamily: "Inter, system-ui, sans-serif",
            boxSizing: "border-box",
            ...badgeCSS,
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
