import React from "react";
import type { KeyValueItem } from "../../types";
import type { CardRendererProps } from "./types";

export const KeyValueContent: React.FC<CardRendererProps<KeyValueItem>> = ({
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: vmin * 0.6,
        width: "100%",
      }}
    >
      {item.pairs.slice(0, 6).map((pair, idx) => (
        <div
          key={idx}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: `${vmin * 0.6}px 0`,
            borderBottom:
              idx < item.pairs.length - 1
                ? `1px solid ${theme.border}`
                : undefined,
          }}
        >
          <span
            style={{
              fontSize: vmin * 1.6,
              fontWeight: 500,
              color: theme.textSecondary,
            }}
          >
            {pair.label}
          </span>
          <span
            style={{
              fontSize: vmin * 1.7,
              fontWeight: 700,
              color: item.color,
            }}
          >
            {pair.value}
          </span>
        </div>
      ))}
    </div>
  </>
);
