/** Group header pill badge for comparison columns. */
import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import type { ThemeColors } from "../../../theme";
import { ITEM_FADE_DURATION } from "../constants";

interface GroupHeaderProps {
  label: string;
  color: string;
  enterFrame: number;
  vmin: number;
  w: number;
  h: number;
  theme: ThemeColors;
}

export const GroupHeader: React.FC<GroupHeaderProps> = ({
  label,
  color,
  enterFrame,
  vmin,
  w,
  h,
  theme,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = frame - enterFrame;

  const opacity = interpolate(
    localFrame,
    [0, ITEM_FADE_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const scale = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 12, stiffness: 100, mass: 0.6 },
  });

  return (
    <div
      style={{
        width: w,
        height: h,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          backgroundColor: `${color}18`,
          border: `${vmin * 0.12}px solid ${color}40`,
          borderRadius: vmin * 2,
          padding: `${vmin * 0.6}px ${vmin * 2}px`,
          fontFamily: "Inter, system-ui, sans-serif",
          fontSize: vmin * 2.2,
          fontWeight: 700,
          color,
        }}
      >
        {label}
      </div>
    </div>
  );
};
