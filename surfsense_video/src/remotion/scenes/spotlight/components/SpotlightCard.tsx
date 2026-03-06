/**
 * SpotlightCard -- shared card shell for all categories.
 * Wraps each card in CardReveal for stroke animation,
 * applies variant background style and glow overlay,
 * then delegates to the category-specific renderer.
 */
import React from "react";
import type { ThemeColors } from "../../../theme";
import type { SpotlightVariant } from "../variant";
import type { CardItem } from "../types";
import { renderCardContent } from "./categories";
import { CardReveal } from "./CardReveal";

interface SpotlightCardProps {
  item: CardItem;
  index: number;
  enterFrame: number;
  vmin: number;
  w: number;
  h: number;
  variant: SpotlightVariant;
  theme: ThemeColors;
}

export const SpotlightCard: React.FC<SpotlightCardProps> = ({
  item, index, enterFrame, vmin, w, h, variant, theme,
}) => {
  if (!item) return null;

  const color = item.color;
  const pad = vmin * 4;
  const radius = vmin * 1.5;

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
    <CardReveal enterFrame={enterFrame} index={index} width={w} height={h}
      radius={radius} color={color} vmin={vmin} reveal={variant.reveal}>
      <div
        style={{
          width: w, height: h,
          position: "relative",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: vmin * 1.5,
          padding: pad,
          fontFamily: "Inter, system-ui, sans-serif",
          overflow: "hidden",
          borderRadius: radius,
          ...bgStyle(),
        }}
      >
        <div style={{
          position: "absolute", inset: 0, borderRadius: radius,
          background: `radial-gradient(ellipse at ${glowX}% ${glowY}%, ${color}${theme.glowOpacity} 0%, transparent 60%)`,
          pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", inset: 0, borderRadius: radius,
          border: `1px solid ${theme.border}`, pointerEvents: "none",
        }} />
        {renderCardContent(item, { index, enterFrame, vmin, theme, variant })}
      </div>
    </CardReveal>
  );
};
