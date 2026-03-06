/** Quote card — large quotation mark, text, author, and role. */
import React from "react";
import type { QuoteItem } from "../../types";
import type { CardRendererProps } from "./types";

export const QuoteContent: React.FC<CardRendererProps<QuoteItem>> = ({
  item, vmin, theme,
}) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
    <div style={{
      fontSize: vmin * 6, fontWeight: 800, color: `${item.color}40`,
      lineHeight: 0.8, userSelect: "none", textAlign: "center",
    }}>
      {"\u201C"}
    </div>
    <div style={{
      fontSize: vmin * 2.6, fontWeight: 500, fontStyle: "italic",
      color: theme.textPrimary, lineHeight: 1.45, textAlign: "center",
      overflow: "hidden", display: "-webkit-box",
      WebkitLineClamp: 4, WebkitBoxOrient: "vertical" as const,
    }}>
      {item.quote}
    </div>
    <div style={{ display: "flex", flexDirection: "column", gap: vmin * 0.3, alignItems: "center", marginTop: vmin * 0.5 }}>
      <div style={{ fontSize: vmin * 1.8, fontWeight: 700, color: item.color, textAlign: "center" }}>
        {item.author}
      </div>
      {item.role && (
        <div style={{ fontSize: vmin * 1.5, fontWeight: 400, color: theme.textSecondary, textAlign: "center" }}>
          {item.role}
        </div>
      )}
    </div>
  </div>
);
