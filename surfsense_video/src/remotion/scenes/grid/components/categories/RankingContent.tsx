import React from "react";
import type { RankingItem } from "../../types";
import type { CardRendererProps } from "./types";

export const RankingContent: React.FC<CardRendererProps<RankingItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => (
  <>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: vmin * 2,
        flexDirection: isCenter ? "column" : "row",
      }}
    >
      <div
        style={{
          width: vmin * 5.5,
          height: vmin * 5.5,
          borderRadius: vmin * 1.2,
          background: `linear-gradient(135deg, ${item.color}, ${item.color}80)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: vmin * 2.8,
          fontWeight: 900,
          color: "#fff",
          flexShrink: 0,
        }}
      >
        #{item.rank}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: vmin * 0.4 }}>
        <div
          style={{
            fontSize: vmin * 3,
            fontWeight: 700,
            color: theme.textPrimary,
            lineHeight: 1.2,
          }}
        >
          {item.title}
        </div>
        {item.value && (
          <div
            style={{
              fontSize: vmin * 2.2,
              fontWeight: 800,
              color: item.color,
            }}
          >
            {item.value}
          </div>
        )}
      </div>
    </div>
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
