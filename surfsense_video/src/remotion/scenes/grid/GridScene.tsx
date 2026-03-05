/**
 * GridScene — main grid scene component.
 *
 * Places all cards as Element3D (always visible in 3D space),
 * then defines Step waypoints that drive the camera between cards.
 */
import React from "react";
import { Scene3D, Step, Element3D, useViewportRect } from "remotion-bits";
import type { ThemeColors } from "../../theme";
import type { GridSceneInput } from "./types";
import type { GridVariant } from "./variant";
import { STEP_DURATION, TRANSITION_DURATION } from "./constants";
import { MemoContentItem } from "./components/ContentItem";

/** 2-column grid layout centered at origin. */
function computePositions(count: number, cellW: number, cellH: number) {
  const cols = 2;
  const rows = Math.ceil(count / cols);

  return Array.from({ length: count }, (_, i) => ({
    x: (i % cols - 0.5) * cellW,
    y: (Math.floor(i / cols) - (rows - 1) / 2) * cellH,
  }));
}

/** Total duration in frames for a grid with `itemCount` cards. */
export function gridSceneDuration(itemCount: number): number {
  return itemCount * STEP_DURATION + (itemCount - 1) * TRANSITION_DURATION;
}

interface GridSceneProps {
  input: GridSceneInput;
  theme: ThemeColors;
  variant: GridVariant;
}

export const GridScene: React.FC<GridSceneProps> = ({ input, theme, variant }) => {
  const { vmin } = useViewportRect();

  const items = input.items;
  const isHoriz = variant.layout === "horizontal";
  const cellW = isHoriz ? vmin * 88 : vmin * 68;
  const cellH = isHoriz ? vmin * 46 : vmin * 53;
  const positions = computePositions(items.length, cellW, cellH);

  return (
    <Scene3D
      perspective={1200}
      transitionDuration={TRANSITION_DURATION}
      easing="easeInOutCubic"
      style={{ background: theme.bg }}
    >
      {items.map((item, i) => (
        <Element3D key={`card-${i}`} x={positions[i].x} y={positions[i].y} z={0} centered>
          <MemoContentItem item={item} index={i} vmin={vmin} variant={variant} theme={theme} />
        </Element3D>
      ))}

      {items.map((_, i) => (
        <Step key={`cam-${i}`} id={`item-${i + 1}`} duration={STEP_DURATION}
          x={positions[i].x} y={positions[i].y} z={0}>
          <div />
        </Step>
      ))}
    </Scene3D>
  );
};
