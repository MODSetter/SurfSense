/** VS divider for comparison layouts. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import type { ComparisonDivider } from "../variant";
import type { DividerInfo } from "../layout";
import { DIVIDER_DELAY, ITEM_FADE_DURATION } from "../constants";

interface DividerProps {
  info: DividerInfo;
  dividerStyle: ComparisonDivider;
  vmin: number;
  theme: ThemeColors;
  leftColor?: string;
  rightColor?: string;
}

export const CompareDivider: React.FC<DividerProps> = ({
  info,
  dividerStyle,
  vmin,
  theme,
  leftColor = "#6c7dff",
  rightColor = "#00c9a7",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (dividerStyle === "none") return null;

  const opacity = interpolate(
    frame - DIVIDER_DELAY,
    [0, ITEM_FADE_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const scale = spring({
    frame: Math.max(0, frame - DIVIDER_DELAY),
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  return (
    <div
      style={{
        position: "absolute",
        left: info.x,
        top: info.y,
        width: info.w,
        height: info.h,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `scale(${scale})`,
        pointerEvents: "none",
        opacity,
      }}
    >
      {dividerStyle === "vs" && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: vmin * 0.5, height: "100%" }}>
          <div
            style={{
              width: vmin * 0.15,
              flex: 1,
              maxHeight: vmin * 20,
              background: `linear-gradient(to bottom, transparent, ${theme.textSecondary}30)`,
            }}
          />
          <div
            style={{
              width: vmin * 7,
              height: vmin * 7,
              borderRadius: "50%",
              background: `linear-gradient(135deg, ${leftColor}, ${rightColor})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: vmin * 2.2,
              fontWeight: 900,
              color: "#fff",
              fontFamily: "Inter, system-ui, sans-serif",
              boxShadow: `0 ${vmin * 0.4}px ${vmin * 2}px ${leftColor}40`,
              flexShrink: 0,
            }}
          >
            VS
          </div>
          <div
            style={{
              width: vmin * 0.15,
              flex: 1,
              maxHeight: vmin * 20,
              background: `linear-gradient(to bottom, ${theme.textSecondary}30, transparent)`,
            }}
          />
        </div>
      )}
      {dividerStyle === "line" && (
        <div
          style={{
            width: vmin * 0.15,
            height: "80%",
            background: `linear-gradient(to bottom, transparent, ${theme.textSecondary}25, transparent)`,
          }}
        />
      )}
    </div>
  );
};
