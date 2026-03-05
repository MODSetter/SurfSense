import React from "react";
import type { ComparisonItem } from "../../types";
import type { CardRendererProps } from "./types";

export const ComparisonContent: React.FC<CardRendererProps<ComparisonItem>> = ({
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
        marginBottom: vmin * 1,
      }}
    >
      {item.title}
    </div>
    <div
      style={{
        display: "flex",
        gap: vmin * 2,
        width: "100%",
      }}
    >
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: vmin * 0.6,
          padding: `${vmin * 1.5}px`,
          borderRadius: vmin * 1,
          background: `${item.color}08`,
          border: `1px solid ${item.color}20`,
        }}
      >
        <div
          style={{
            fontSize: vmin * 1.4,
            fontWeight: 600,
            color: theme.textSecondary,
            textTransform: "uppercase",
            letterSpacing: vmin * 0.05,
          }}
        >
          {item.labelA}
        </div>
        <div
          style={{
            fontSize: vmin * 3.5,
            fontWeight: 800,
            color: item.color,
          }}
        >
          {item.valueA}
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          fontSize: vmin * 2,
          fontWeight: 600,
          color: theme.textMuted,
        }}
      >
        vs
      </div>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: vmin * 0.6,
          padding: `${vmin * 1.5}px`,
          borderRadius: vmin * 1,
          background: `${item.color}08`,
          border: `1px solid ${item.color}20`,
        }}
      >
        <div
          style={{
            fontSize: vmin * 1.4,
            fontWeight: 600,
            color: theme.textSecondary,
            textTransform: "uppercase",
            letterSpacing: vmin * 0.05,
          }}
        >
          {item.labelB}
        </div>
        <div
          style={{
            fontSize: vmin * 3.5,
            fontWeight: 800,
            color: item.color,
          }}
        >
          {item.valueB}
        </div>
      </div>
    </div>
  </>
);
