import React from "react";
import type { StepItem } from "../../types";
import type { CardRendererProps } from "./types";

export const StepContent: React.FC<CardRendererProps<StepItem>> = ({
  item,
  vmin,
  theme,
  isCenter,
}) => (
  <>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: vmin * 2,
        flexDirection: isCenter ? "column" : "row",
      }}
    >
      <div
        style={{
          width: vmin * 5.5,
          height: vmin * 5.5,
          borderRadius: "50%",
          background: `linear-gradient(135deg, ${item.color}, ${item.color}80)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: vmin * 2.5,
          fontWeight: 900,
          color: "#fff",
          flexShrink: 0,
        }}
      >
        {item.step}
      </div>
      <div
        style={{
          fontSize: vmin * 3,
          fontWeight: 700,
          color: theme.textPrimary,
          lineHeight: 1.2,
        }}
      >
        {item.title}
      </div>
    </div>
    {item.desc && (
      <div
        style={{
          fontSize: vmin * 1.8,
          fontWeight: 400,
          color: theme.textMuted,
          lineHeight: 1.55,
          textAlign: isCenter ? "center" : "left",
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 3,
          WebkitBoxOrient: "vertical" as const,
        }}
      >
        {item.desc}
      </div>
    )}
  </>
);
