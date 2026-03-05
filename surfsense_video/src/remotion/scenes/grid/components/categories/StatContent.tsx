import React from "react";
import type { StatItem } from "../../types";
import type { CardRendererProps } from "./types";

export const StatContent: React.FC<CardRendererProps<StatItem>> = ({
  item,
  vmin,
  theme,
  variant,
  isCenter,
}) => {
  const isHero = variant.valueStyle === "hero" || variant.valueStyle === "colored";

  return (
    <>
      {isHero && (
        <div
          style={{
            fontSize: vmin * 2.1,
            fontWeight: 600,
            color: theme.textSecondary,
            letterSpacing: vmin * 0.06,
            textTransform: "uppercase",
            textAlign: isCenter ? "center" : "left",
          }}
        >
          {item.title}
        </div>
      )}
      <div
        style={{
          fontSize: variant.valueStyle === "hero" ? vmin * 8 : vmin * 6,
          fontWeight: 800,
          color: variant.valueStyle === "colored" ? item.color : theme.textPrimary,
          lineHeight: 1,
          letterSpacing: `-${vmin * 0.12}px`,
          whiteSpace: "nowrap",
          textShadow:
            variant.valueStyle === "colored"
              ? `0 0 ${vmin * 3}px ${item.color}35`
              : undefined,
        }}
      >
        {item.value}
      </div>
      {!isHero && (
        <div
          style={{
            fontSize: vmin * 3.2,
            fontWeight: 700,
            color: theme.textPrimary,
            lineHeight: 1.25,
            textAlign: isCenter ? "center" : "left",
          }}
        >
          {item.title}
        </div>
      )}
      {item.desc && (
        <div
          style={{
            fontSize: vmin * 1.8,
            fontWeight: 400,
            color: theme.textMuted,
            lineHeight: 1.55,
            textAlign: isCenter ? "center" : "left",
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical" as const,
          }}
        >
          {item.desc}
        </div>
      )}
    </>
  );
};
