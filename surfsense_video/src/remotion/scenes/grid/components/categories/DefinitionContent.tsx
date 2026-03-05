import React from "react";
import type { DefinitionItem } from "../../types";
import type { CardRendererProps } from "./types";

export const DefinitionContent: React.FC<CardRendererProps<DefinitionItem>> = ({
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
        color: item.color,
        lineHeight: 1.2,
        textAlign: isCenter ? "center" : "left",
        fontStyle: "italic",
      }}
    >
      {item.term}
    </div>
    <div
      style={{
        width: isCenter ? vmin * 5 : vmin * 7,
        height: 2,
        background: `linear-gradient(90deg, ${isCenter ? "transparent" : item.color}, ${item.color}, transparent)`,
        borderRadius: 1,
        alignSelf: isCenter ? "center" : "flex-start",
      }}
    />
    <div
      style={{
        fontSize: vmin * 2,
        fontWeight: 400,
        color: theme.textPrimary,
        lineHeight: 1.55,
        textAlign: isCenter ? "center" : "left",
        overflow: "hidden",
        display: "-webkit-box",
        WebkitLineClamp: 4,
        WebkitBoxOrient: "vertical" as const,
      }}
    >
      {item.definition}
    </div>
    {item.example && (
      <div
        style={{
          fontSize: vmin * 1.6,
          fontWeight: 500,
          fontStyle: "italic",
          color: theme.textSecondary,
          textAlign: isCenter ? "center" : "left",
        }}
      >
        e.g. {item.example}
      </div>
    )}
  </>
);
