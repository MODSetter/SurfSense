/** Info card — title, subtitle, description, and optional tag badge. */
import React from "react";
import type { InfoItem } from "../../types";
import type { CardRendererProps } from "./types";

export const InfoContent: React.FC<CardRendererProps<InfoItem>> = ({
  item, vmin, theme,
}) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
    {item.tag && (
      <div style={{
        display: "inline-flex",
        padding: `${vmin * 0.3}px ${vmin * 1}px`,
        borderRadius: vmin * 0.5,
        background: `${item.color}${theme.badgeBg}`,
        border: `1px solid ${item.color}${theme.badgeBorder}`,
        fontSize: vmin * 1.4, fontWeight: 600, color: item.color,
        textTransform: "uppercase", letterSpacing: vmin * 0.05, alignSelf: "center",
      }}>
        {item.tag}
      </div>
    )}
    <div style={{
      fontSize: vmin * 3.2, fontWeight: 700, color: theme.textPrimary,
      lineHeight: 1.25, textAlign: "center", overflow: "hidden", textOverflow: "ellipsis",
      display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const,
    }}>
      {item.title}
    </div>
    {item.subtitle && (
      <div style={{
        fontSize: vmin * 1.8, fontWeight: 500, color: theme.textSecondary,
        lineHeight: 1.3, textAlign: "center",
      }}>
        {item.subtitle}
      </div>
    )}
    <div style={{
      fontSize: vmin * 1.8, fontWeight: 400, color: theme.textMuted,
      lineHeight: 1.55, textAlign: "center", overflow: "hidden",
      display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" as const,
    }}>
      {item.desc}
    </div>
  </div>
);
