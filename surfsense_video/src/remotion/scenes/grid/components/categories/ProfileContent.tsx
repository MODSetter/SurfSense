/** Profile card — avatar initials, name, role, optional tag and description. */
import React from "react";
import type { ProfileItem } from "../../types";
import type { CardRendererProps } from "./types";

export const ProfileContent: React.FC<CardRendererProps<ProfileItem>> = ({
  item, vmin, theme,
}) => {
  const initials = item.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: vmin * 2, flexDirection: "column" }}>
        <div style={{
          width: vmin * 7, height: vmin * 7, borderRadius: "50%",
          background: `linear-gradient(135deg, ${item.color}, ${item.color}80)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: vmin * 2.5, fontWeight: 800, color: "#fff", flexShrink: 0,
        }}>
          {initials}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: vmin * 0.4, alignItems: "center" }}>
          <div style={{ fontSize: vmin * 3, fontWeight: 700, color: theme.textPrimary, lineHeight: 1.2, textAlign: "center" }}>
            {item.name}
          </div>
          <div style={{ fontSize: vmin * 1.8, fontWeight: 500, color: item.color, textAlign: "center" }}>
            {item.role}
          </div>
        </div>
      </div>
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
      {item.desc && (
        <div style={{
          fontSize: vmin * 1.8, fontWeight: 400, color: theme.textMuted,
          lineHeight: 1.55, textAlign: "center", overflow: "hidden",
          display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" as const,
        }}>
          {item.desc}
        </div>
      )}
    </div>
  );
};
