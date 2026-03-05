import React from "react";
import type { ListItem } from "../../types";
import type { CardRendererProps } from "./types";

export const ListContent: React.FC<CardRendererProps<ListItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => (
  <>
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
    {item.subtitle && (
      <div
        style={{
          fontSize: vmin * 1.8,
          fontWeight: 500,
          color: theme.textSecondary,
          lineHeight: 1.3,
          textAlign: isCenter ? "center" : "left",
        }}
      >
        {item.subtitle}
      </div>
    )}
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: vmin * 0.8,
        overflow: "hidden",
      }}
    >
      {item.bullets.slice(0, 5).map((b, idx) => (
        <div
          key={idx}
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: vmin * 0.8,
            fontSize: vmin * 1.7,
            color: theme.textMuted,
            lineHeight: 1.4,
          }}
        >
          <div
            style={{
              width: vmin * 0.5,
              height: vmin * 0.5,
              borderRadius: "50%",
              background: item.color,
              flexShrink: 0,
              marginTop: vmin * 0.5,
            }}
          />
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {b}
          </span>
        </div>
      ))}
    </div>
  </>
);
