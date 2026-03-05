import React, { memo } from "react";
import type { ThemeColors } from "../../../theme";
import type { GridVariant } from "../variant";
import type { CardItem } from "../types";
import { renderCardContent } from "./categories";

interface ContentItemProps {
  item: CardItem;
  vmin: number;
  variant: GridVariant;
  theme: ThemeColors;
}

const ContentItem: React.FC<ContentItemProps> = ({
  item,
  vmin,
  variant,
  theme,
}) => {
  if (!item) return null;

  const color = item.color;
  const isCenter = variant.align === "center";
  const isHoriz = variant.layout === "horizontal";
  const w = isHoriz ? vmin * 72 : vmin * 52;
  const h = isHoriz ? vmin * 32 : vmin * 38;
  const accentThick = vmin * 0.4;
  const pad = vmin * 4;

  const glowX = 50 + 40 * Math.cos((variant.glowAngle * Math.PI) / 180);
  const glowY = 50 + 40 * Math.sin((variant.glowAngle * Math.PI) / 180);

  type AccentSide = "left" | "top" | "bottom" | "right";
  const isVBar = variant.accent === "left" || variant.accent === "right";
  const accentPos: Record<AccentSide, React.CSSProperties> = {
    left: { left: 0, top: pad, bottom: pad, width: accentThick },
    right: { right: 0, top: pad, bottom: pad, width: accentThick },
    top: { top: 0, left: pad, right: pad, height: accentThick },
    bottom: { bottom: 0, left: pad, right: pad, height: accentThick },
  };

  return (
    <div
      style={{
        width: w,
        height: h,
        position: "relative",
        display: "flex",
        flexDirection: isHoriz ? "row" : "column",
        alignItems: isHoriz ? "center" : isCenter ? "center" : "flex-start",
        justifyContent: isHoriz ? "flex-start" : "center",
        gap: isHoriz ? vmin * 4 : vmin * 1.5,
        padding: pad,
        fontFamily: "Inter, system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: vmin * 1.5,
          background: `radial-gradient(ellipse at ${glowX}% ${glowY}%, ${color}${theme.glowOpacity} 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: vmin * 1.5,
          border: `1px solid ${theme.border}`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          ...accentPos[variant.accent],
          borderRadius: accentThick,
          background: `linear-gradient(${isVBar ? "180deg" : "90deg"}, ${color}, ${color}30)`,
          boxShadow: `0 0 ${vmin * 1.2}px ${color}${theme.accentGlowSuffix}`,
        }}
      />
      {renderCardContent(item, { vmin, theme, variant, isCenter })}
    </div>
  );
};

export const MemoContentItem = memo(ContentItem);
