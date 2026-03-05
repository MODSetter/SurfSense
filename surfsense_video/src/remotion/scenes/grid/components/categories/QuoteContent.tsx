import React from "react";
import type { QuoteItem } from "../../types";
import type { CardRendererProps } from "./types";

export const QuoteContent: React.FC<CardRendererProps<QuoteItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => (
  <>
    <div
      style={{
        fontSize: vmin * 6,
        fontWeight: 800,
        color: `${item.color}40`,
        lineHeight: 0.8,
        userSelect: "none",
        textAlign: isCenter ? "center" : "left",
      }}
    >
      {"\u201C"}
    </div>
    <div
      style={{
        fontSize: vmin * 2.6,
        fontWeight: 500,
        fontStyle: "italic",
        color: theme.textPrimary,
        lineHeight: 1.45,
        textAlign: isCenter ? "center" : "left",
        overflow: "hidden",
        display: "-webkit-box",
        WebkitLineClamp: 4,
        WebkitBoxOrient: "vertical" as const,
      }}
    >
      {item.quote}
    </div>
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: vmin * 0.3,
        alignItems: isCenter ? "center" : "flex-start",
        marginTop: vmin * 0.5,
      }}
    >
      <div
        style={{
          fontSize: vmin * 1.8,
          fontWeight: 700,
          color: item.color,
        }}
      >
        {item.author}
      </div>
      {item.role && (
        <div
          style={{
            fontSize: vmin * 1.5,
            fontWeight: 400,
            color: theme.textSecondary,
          }}
        >
          {item.role}
        </div>
      )}
    </div>
  </>
);
