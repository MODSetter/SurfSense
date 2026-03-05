import React from "react";
import type { FactItem } from "../../types";
import type { CardRendererProps } from "./types";

export const FactContent: React.FC<CardRendererProps<FactItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => (
  <>
    <div
      style={{
        fontSize: vmin * 3.5,
        fontWeight: 800,
        color: theme.textPrimary,
        lineHeight: 1.3,
        textAlign: isCenter ? "center" : "left",
        overflow: "hidden",
        display: "-webkit-box",
        WebkitLineClamp: 4,
        WebkitBoxOrient: "vertical" as const,
      }}
    >
      {item.statement}
    </div>
    {item.source && (
      <div
        style={{
          fontSize: vmin * 1.5,
          fontWeight: 500,
          color: item.color,
          textAlign: isCenter ? "center" : "left",
          marginTop: vmin * 0.5,
        }}
      >
        {item.source}
      </div>
    )}
  </>
);
