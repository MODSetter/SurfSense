import React from "react";
import { useScene3D } from "remotion-bits";

export const ItemScale: React.FC<{
  stepId: string;
  children: React.ReactNode;
}> = ({ stepId, children }) => {
  const { activeStepId, transitionProgress, steps, activeStepIndex } =
    useScene3D();

  const small = 0.85;
  const big = 1.3;

  const isMe = activeStepId === stepId;
  const prevId =
    activeStepIndex > 0 ? steps[activeStepIndex - 1]?.id ?? "" : "";
  const wasMe = prevId === stepId;

  let scale: number;
  if (isMe) {
    scale = small + (big - small) * transitionProgress;
  } else if (wasMe && transitionProgress < 1) {
    scale = big - (big - small) * transitionProgress;
  } else {
    scale = small;
  }

  return (
    <div style={{ transform: `scale(${scale})`, willChange: "transform" }}>
      {children}
    </div>
  );
};
