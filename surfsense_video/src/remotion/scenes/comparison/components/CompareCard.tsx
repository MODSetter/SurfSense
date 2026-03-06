/** Single comparison item card with variant-driven styling. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { CompareItem } from "../types";
import type { ComparisonCardStyle } from "../variant";
import { ITEM_FADE_DURATION } from "../constants";

interface CompareCardProps {
  item: CompareItem;
  enterFrame: number;
  vmin: number;
  w: number;
  h: number;
  color: string;
  cardStyle: ComparisonCardStyle;
  theme: ThemeColors;
}

function cardCSS(
  style: ComparisonCardStyle,
  color: string,
  vmin: number,
): React.CSSProperties {
  const bw = vmin * 0.14;

  switch (style) {
    case "gradient":
      return {
        background: `linear-gradient(145deg, ${color}14, ${color}06)`,
        border: `${bw}px solid ${color}35`,
        boxShadow: `0 ${vmin * 0.4}px ${vmin * 1.5}px ${color}10`,
      };
    case "glass":
      return {
        background: `${color}0a`,
        backdropFilter: "blur(12px)",
        border: `${bw}px solid ${color}20`,
        boxShadow: `inset 0 ${vmin * 0.1}px ${vmin * 0.5}px ${color}12`,
      };
    case "outline":
      return {
        background: "transparent",
        border: `${vmin * 0.18}px solid ${color}55`,
      };
    case "solid":
      return {
        background: `${color}15`,
        border: `${bw}px solid ${color}28`,
      };
  }
}

export const CompareCard: React.FC<CompareCardProps> = ({
  item,
  enterFrame,
  vmin,
  w,
  h,
  color,
  cardStyle,
  theme,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - enterFrame;

  const opacity = interpolate(
    localFrame,
    [0, ITEM_FADE_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const scale = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.5 },
  });

  const fontSize = vmin * 2;
  const descFontSize = vmin * 1.5;

  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: vmin * 0.8,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: `${vmin * 1.5}px ${vmin * 2.5}px`,
        boxSizing: "border-box",
        opacity,
        transform: `scale(${scale})`,
        ...cardCSS(cardStyle, color, vmin),
      }}
    >
      <div
        style={{
          color: theme.textPrimary,
          fontSize,
          fontWeight: 600,
          fontFamily: "Inter, system-ui, sans-serif",
          lineHeight: 1.3,
        }}
      >
        {item.label}
      </div>
      {item.desc && (
        <div
          style={{
            color: theme.textSecondary,
            fontSize: descFontSize,
            fontWeight: 400,
            fontFamily: "Inter, system-ui, sans-serif",
            lineHeight: 1.3,
            marginTop: vmin * 0.35,
          }}
        >
          {item.desc}
        </div>
      )}
    </div>
  );
};
