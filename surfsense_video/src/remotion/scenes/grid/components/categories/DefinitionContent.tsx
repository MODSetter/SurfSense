/** Definition card — term, definition, and optional usage example. */
import React from "react";
import type { DefinitionItem } from "../../types";
import type { CardRendererProps } from "./types";

export const DefinitionContent: React.FC<CardRendererProps<DefinitionItem>> = ({
  item, vmin, theme,
}) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
    <div style={{
      fontSize: vmin * 3.5, fontWeight: 800, color: item.color,
      lineHeight: 1.2, textAlign: "center", fontStyle: "italic",
    }}>
      {item.term}
    </div>
    <div style={{
      width: vmin * 5, height: 2,
      background: `linear-gradient(90deg, transparent, ${item.color}, transparent)`,
      borderRadius: 1, alignSelf: "center",
    }} />
    <div style={{
      fontSize: vmin * 2, fontWeight: 400, color: theme.textPrimary,
      lineHeight: 1.55, textAlign: "center", overflow: "hidden",
      display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical" as const,
    }}>
      {item.definition}
    </div>
    {item.example && (
      <div style={{
        fontSize: vmin * 1.6, fontWeight: 500, fontStyle: "italic",
        color: theme.textSecondary, textAlign: "center",
      }}>
        e.g. {item.example}
      </div>
    )}
  </div>
);
