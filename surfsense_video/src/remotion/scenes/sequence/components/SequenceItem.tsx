/** Single sequence step — card with style determined by variant.cardStyle. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { SequenceItem as SequenceItemData } from "../types";
import type { SequenceVariant, SequenceCardStyle } from "../variant";
import { ITEM_FADE_DURATION } from "../constants";

interface SequenceItemProps {
  item: SequenceItemData;
  index: number;
  enterFrame: number;
  vmin: number;
  variant: SequenceVariant;
  theme: ThemeColors;
  cardWidth: number;
  cardHeight: number;
}

function seqCardCSS(
  style: SequenceCardStyle,
  color: string,
  vmin: number,
): { card: React.CSSProperties; showTopBar: boolean } {
  const bw = vmin * 0.14;

  switch (style) {
    case "top-bar":
      return {
        showTopBar: true,
        card: {
          background: `linear-gradient(90deg, ${color}18, ${color}08)`,
          border: `${bw}px solid ${color}15`,
          boxShadow: `0 0 ${vmin * 3}px ${color}0c`,
        },
      };
    case "glow":
      return {
        showTopBar: false,
        card: {
          background: `${color}10`,
          border: `${bw}px solid ${color}30`,
          boxShadow: `0 0 ${vmin * 4}px ${color}25, 0 0 ${vmin * 1.5}px ${color}15`,
        },
      };
    case "bordered":
      return {
        showTopBar: false,
        card: {
          background: `linear-gradient(135deg, ${color}0c, ${color}04)`,
          border: `${vmin * 0.22}px solid ${color}88`,
          boxShadow: `0 ${vmin * 0.3}px ${vmin * 1.5}px rgba(0,0,0,0.15)`,
        },
      };
    case "minimal":
      return {
        showTopBar: false,
        card: {
          background: `${color}08`,
          border: `${bw}px solid ${color}12`,
          boxShadow: "none",
        },
      };
  }
}

function seqBadgeCSS(
  style: SequenceCardStyle,
  color: string,
  vmin: number,
): React.CSSProperties {
  switch (style) {
    case "top-bar":
      return { background: "transparent", border: `${vmin * 0.25}px solid ${color}`, color };
    case "glow":
      return { background: color, color: "#fff", boxShadow: `0 0 ${vmin * 2}px ${color}40` };
    case "bordered":
      return { background: `${color}30`, color, border: `${vmin * 0.15}px solid ${color}66` };
    case "minimal":
      return { background: "transparent", color: `${color}aa`, fontWeight: 600 };
  }
}

export const SequenceItemCard: React.FC<SequenceItemProps> = ({
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
  const { card: styleCSS, showTopBar } = seqCardCSS(variant.cardStyle, color, vmin);
  const badgeCSS = seqBadgeCSS(variant.cardStyle, color, vmin);
  const topBarH = vmin * 0.35;

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
        paddingTop: showTopBar ? paddingY + topBarH : paddingY,
        borderRadius,
        overflow: "hidden",
        ...styleCSS,
      }}
    >
      {showTopBar && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: topBarH,
            background: `linear-gradient(90deg, ${color}, ${color}66)`,
            borderRadius: `${borderRadius}px ${borderRadius}px 0 0`,
          }}
        />
      )}
      {variant.showStepNumber && (
        <div
          style={{
            flexShrink: 0,
            width: vmin * 5,
            height: vmin * 5,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: vmin * 1.8,
            fontWeight: 700,
            fontFamily: "Inter, system-ui, sans-serif",
            boxSizing: "border-box",
            ...badgeCSS,
          }}
        >
          {String(index + 1).padStart(2, "0")}
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
