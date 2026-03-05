import React from "react";
import type { ProgressItem } from "../../types";
import type { CardRendererProps } from "./types";

export const ProgressContent: React.FC<CardRendererProps<ProgressItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => {
  const max = item.max ?? 100;
  const pct = Math.min(Math.max(item.value / max, 0), 1);

  return (
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
          alignItems: "baseline",
          gap: vmin * 0.5,
          justifyContent: isCenter ? "center" : "flex-start",
        }}
      >
        <span
          style={{
            fontSize: vmin * 5,
            fontWeight: 800,
            color: item.color,
            lineHeight: 1,
          }}
        >
          {item.value}
        </span>
        <span
          style={{
            fontSize: vmin * 2,
            fontWeight: 500,
            color: theme.textSecondary,
          }}
        >
          {item.max ? `/ ${item.max}` : "%"}
        </span>
      </div>
      <div
        style={{
          width: "100%",
          height: vmin * 1,
          borderRadius: vmin * 0.5,
          background: theme.border,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct * 100}%`,
            height: "100%",
            borderRadius: vmin * 0.5,
            background: `linear-gradient(90deg, ${item.color}, ${item.color}cc)`,
            boxShadow: `0 0 ${vmin * 1}px ${item.color}50`,
          }}
        />
      </div>
      {item.desc && (
        <div
          style={{
            fontSize: vmin * 1.8,
            fontWeight: 400,
            color: theme.textMuted,
            lineHeight: 1.55,
            textAlign: isCenter ? "center" : "left",
          }}
        >
          {item.desc}
        </div>
      )}
    </>
  );
};
