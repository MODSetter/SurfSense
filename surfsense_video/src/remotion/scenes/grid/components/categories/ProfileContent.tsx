import React from "react";
import type { ProfileItem } from "../../types";
import type { CardRendererProps } from "./types";

export const ProfileContent: React.FC<CardRendererProps<ProfileItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => {
  const initials = item.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: isCenter ? "center" : "flex-start",
          gap: vmin * 2,
          flexDirection: isCenter ? "column" : "row",
        }}
      >
        <div
          style={{
            width: vmin * 7,
            height: vmin * 7,
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${item.color}, ${item.color}80)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: vmin * 2.5,
            fontWeight: 800,
            color: "#fff",
            flexShrink: 0,
          }}
        >
          {initials}
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: vmin * 0.4,
          }}
        >
          <div
            style={{
              fontSize: vmin * 3,
              fontWeight: 700,
              color: theme.textPrimary,
              lineHeight: 1.2,
            }}
          >
            {item.name}
          </div>
          <div
            style={{
              fontSize: vmin * 1.8,
              fontWeight: 500,
              color: item.color,
            }}
          >
            {item.role}
          </div>
        </div>
      </div>
      {item.tag && (
        <div
          style={{
            display: "inline-flex",
            padding: `${vmin * 0.3}px ${vmin * 1}px`,
            borderRadius: vmin * 0.5,
            background: `${item.color}${theme.badgeBg}`,
            border: `1px solid ${item.color}${theme.badgeBorder}`,
            fontSize: vmin * 1.4,
            fontWeight: 600,
            color: item.color,
            textTransform: "uppercase",
            letterSpacing: vmin * 0.05,
            alignSelf: isCenter ? "center" : "flex-start",
          }}
        >
          {item.tag}
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
