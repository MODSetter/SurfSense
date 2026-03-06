/** Progress card -- animated bar with spring physics. */
import React from "react";
import { useCurrentFrame, spring, useVideoConfig } from "remotion";
import type { ProgressItem } from "../../types";
import type { CardRendererProps } from "./types";

interface ProgressProps extends CardRendererProps<ProgressItem> {
  enterFrame: number;
}

export const ProgressContent: React.FC<ProgressProps> = ({
  item, enterFrame, vmin, theme,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const max = item.max ?? 100;
  const pct = Math.min(Math.max(item.value / max, 0), 1);

  const localFrame = Math.max(0, frame - enterFrame);

  const barProgress = spring({
    frame: localFrame, fps,
    config: { damping: 18, stiffness: 40, mass: 1.2 },
  });
  const animatedPct = pct * barProgress;
  const displayValue = Math.round(item.value * barProgress);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", gap: vmin * 1.5 }}>
      <div style={{
        fontSize: vmin * 3.2, fontWeight: 700, color: theme.textPrimary,
        lineHeight: 1.25, textAlign: "center",
      }}>
        {item.title}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: vmin * 0.5, justifyContent: "center" }}>
        <span style={{ fontSize: vmin * 5, fontWeight: 800, color: item.color, lineHeight: 1 }}>
          {displayValue}
        </span>
        <span style={{ fontSize: vmin * 2, fontWeight: 500, color: theme.textSecondary }}>
          {item.max ? `/ ${item.max}` : "%"}
        </span>
      </div>
      <div style={{
        width: "100%", height: vmin * 1, borderRadius: vmin * 0.5,
        background: theme.border, overflow: "hidden",
      }}>
        <div style={{
          width: `${animatedPct * 100}%`, height: "100%", borderRadius: vmin * 0.5,
          background: `linear-gradient(90deg, ${item.color}, ${item.color}cc)`,
          boxShadow: `0 0 ${vmin * 1}px ${item.color}50`,
        }} />
      </div>
      {item.desc && (
        <div style={{
          fontSize: vmin * 1.8, fontWeight: 400, color: theme.textMuted,
          lineHeight: 1.55, textAlign: "center",
        }}>
          {item.desc}
        </div>
      )}
    </div>
  );
};
