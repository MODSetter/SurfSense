/** Fact card -- bold statement with optional source attribution. */
import React from "react";
import type { FactItem } from "../../types";
import type { CardRendererProps } from "./types";

export const FactContent: React.FC<CardRendererProps<FactItem>> = ({
  item, vmin, theme,
}) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
    <div style={{
      fontSize: vmin * 3.5, fontWeight: 800, color: theme.textPrimary,
      lineHeight: 1.3, textAlign: "center", overflow: "hidden",
      display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical" as const,
    }}>
      {item.statement}
    </div>
    {item.source && (
      <div style={{
        fontSize: vmin * 1.5, fontWeight: 500, color: item.color,
        textAlign: "center", marginTop: vmin * 0.5,
      }}>
        {item.source}
      </div>
    )}
  </div>
);
