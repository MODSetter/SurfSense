import React from "react";
import { interpolate } from "remotion";
import { evolvePath } from "@remotion/paths";
import { useScene3D } from "remotion-bits";

function roundedRectPath(w: number, h: number, r: number): string {
  return [
    `M ${r} 0`,
    `L ${w - r} 0`,
    `Q ${w} 0 ${w} ${r}`,
    `L ${w} ${h - r}`,
    `Q ${w} ${h} ${w - r} ${h}`,
    `L ${r} ${h}`,
    `Q 0 ${h} 0 ${h - r}`,
    `L 0 ${r}`,
    `Q 0 0 ${r} 0`,
    "Z",
  ].join(" ");
}

export const DrawingReveal: React.FC<{
  stepId: string;
  width: number;
  height: number;
  radius: number;
  color: string;
  vmin: number;
  reveal: "drawing" | "instant" | "fade";
  children: React.ReactNode;
}> = ({ stepId, width, height, radius, color, vmin, reveal, children }) => {
  const { activeStepId, transitionProgress, steps, activeStepIndex } =
    useScene3D();

  if (reveal === "instant") {
    return <>{children}</>;
  }

  const isMe = activeStepId === stepId;
  const prevId =
    activeStepIndex > 0 ? steps[activeStepIndex - 1]?.id ?? "" : "";
  const wasMe = prevId === stepId;

  let drawProgress: number;
  let contentOpacity: number;

  if (isMe) {
    drawProgress = transitionProgress;
    contentOpacity = interpolate(transitionProgress, [0.5, 1], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (wasMe && transitionProgress < 1) {
    drawProgress = 1;
    contentOpacity = interpolate(transitionProgress, [0, 0.5], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else {
    const myIndex = steps.findIndex((s) => s.id === stepId);
    const alreadyVisited = myIndex >= 0 && activeStepIndex > myIndex;
    drawProgress = 0;
    contentOpacity = alreadyVisited ? 1 : 0;
  }

  if (reveal === "fade") {
    return <div style={{ opacity: contentOpacity }}>{children}</div>;
  }

  const path = roundedRectPath(width, height, radius);
  const { strokeDasharray, strokeDashoffset } = evolvePath(
    Math.min(Math.max(drawProgress, 0), 1),
    path,
  );

  const strokeOpacity = drawProgress > 0 && drawProgress < 1 ? 1 : 0;

  return (
    <div style={{ position: "relative", width, height }}>
      <svg
        width={width}
        height={height}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          pointerEvents: "none",
          overflow: "visible",
        }}
      >
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth={vmin * 0.06}
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          opacity={strokeOpacity}
          style={{
            filter: `drop-shadow(0 0 ${vmin * 0.8}px ${color}80)`,
          }}
        />
      </svg>
      <div style={{ position: "relative", opacity: contentOpacity }}>
        {children}
      </div>
    </div>
  );
};
