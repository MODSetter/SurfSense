/**
 * ContentItem — shared card shell for all categories.
 *
 * Wraps each card in CardReveal for stroke animation,
 * applies the variant's background style and glow overlay,
 * then delegates to the category-specific renderer.
 */
import React, { memo } from "react";
import type { ThemeColors } from "../../../theme";
import type { GridVariant } from "../variant";
import type { CardItem } from "../types";
import { renderCardContent } from "./categories";
import { CardReveal } from "./CardReveal";

interface ContentItemProps {
  item: CardItem;
  index: number;
  vmin: number;
  variant: GridVariant;
  theme: ThemeColors;
}

const ContentItem: React.FC<ContentItemProps> = ({ item, index, vmin, variant, theme }) => {
  if (!item) return null;

  const color = item.color;
  const isCenter = variant.align === "center";
  const isHoriz = variant.layout === "horizontal";
  const w = isHoriz ? vmin * 80 : vmin * 60;
  const h = isHoriz ? vmin * 38 : vmin * 45;
  const pad = vmin * 4;
  const radius = vmin * 1.5;

  // Per-card glow position using golden angle offset
  const cardAngle = variant.glowAngle + index * 137.5;
  const glowX = 50 + 40 * Math.cos((cardAngle * Math.PI) / 180);
  const glowY = 50 + 40 * Math.sin((cardAngle * Math.PI) / 180);

  const bgStyle = (): React.CSSProperties => {
    switch (variant.cardBg) {
      case "glass":
        return {
          background: `linear-gradient(135deg, ${color}12 0%, ${color}06 100%)`,
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        };
      case "gradient":
        return {
          background: `linear-gradient(${cardAngle}deg, ${color}18 0%, transparent 50%, ${color}10 100%)`,
        };
      case "subtle":
        return {
          background: `radial-gradient(ellipse at ${glowX}% ${glowY}%, ${color}15 0%, ${color}05 40%, transparent 70%)`,
        };
      case "solid":
      default:
        return {};
    }
  };

  return (
    <CardReveal index={index} width={w} height={h} radius={radius}
      color={color} vmin={vmin} reveal={variant.reveal}>
      <div
        style={{
          width: w, height: h,
          position: "relative",
          display: "flex",
          flexDirection: isHoriz ? "row" : "column",
          alignItems: isHoriz ? "center" : isCenter ? "center" : "flex-start",
          justifyContent: isHoriz ? "flex-start" : "center",
          gap: isHoriz ? vmin * 4 : vmin * 1.5,
          padding: pad,
          fontFamily: "Inter, system-ui, sans-serif",
          overflow: "hidden",
          borderRadius: radius,
          ...bgStyle(),
        }}
      >
        {/* Glow overlay */}
        <div style={{
          position: "absolute", inset: 0, borderRadius: radius,
          background: `radial-gradient(ellipse at ${glowX}% ${glowY}%, ${color}${theme.glowOpacity} 0%, transparent 60%)`,
          pointerEvents: "none",
        }} />

        {/* Border */}
        <div style={{
          position: "absolute", inset: 0, borderRadius: radius,
          border: `1px solid ${theme.border}`, pointerEvents: "none",
        }} />

        {renderCardContent(item, { index, vmin, theme, variant, isCenter })}
      </div>
    </CardReveal>
  );
};

export const MemoContentItem = memo(ContentItem);
