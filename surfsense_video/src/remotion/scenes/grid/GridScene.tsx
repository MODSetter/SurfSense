import React from "react";
import {
  Scene3D,
  Step,
  Element3D,
  GradientTransition,
  useViewportRect,
} from "remotion-bits";
import type { ThemeColors } from "../../theme";
import type { GridSceneInput } from "./types";
import type { GridVariant } from "./variant";
import { STEP_DURATION, TRANSITION_DURATION } from "./constants";
import { MemoContentItem } from "./components/ContentItem";
import { DrawingReveal } from "./components/DrawingReveal";
import { ItemScale } from "./components/ItemScale";

function computePositions(count: number, cellW: number, cellH: number) {
  const cols = 2;
  const rows = Math.ceil(count / cols);

  return Array.from({ length: count }, (_, i) => ({
    x: (i % cols - 0.5) * cellW,
    y: (Math.floor(i / cols) - (rows - 1) / 2) * cellH,
    rotateY: 0,
    rotateX: 0,
  }));
}

function buildGradients(
  colors: string[],
  base: [string, string, string],
): [string, string] {
  const c = colors.length > 0 ? colors : ["#3b82f6"];
  const a = c[0 % c.length];
  const b = c[1 % c.length] ?? a;
  const cc = c[2 % c.length] ?? a;
  const d = c[3 % c.length] ?? b;

  return [
    `radial-gradient(circle at 20% 30%, ${a}25 0%, transparent 40%),
     radial-gradient(circle at 80% 70%, ${b}20 0%, transparent 40%),
     linear-gradient(135deg, ${base[0]} 0%, ${base[1]} 50%, ${base[2]} 100%)`,
    `radial-gradient(circle at 80% 30%, ${cc}25 0%, transparent 40%),
     radial-gradient(circle at 20% 70%, ${d}20 0%, transparent 40%),
     linear-gradient(225deg, ${base[0]} 0%, ${base[1]} 50%, ${base[2]} 100%)`,
  ];
}

export function gridSceneDuration(itemCount: number): number {
  return itemCount * STEP_DURATION + (itemCount - 1) * TRANSITION_DURATION;
}

interface GridSceneProps {
  input: GridSceneInput;
  theme: ThemeColors;
  variant: GridVariant;
}

export const GridScene: React.FC<GridSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const rect = useViewportRect();
  const { vmin } = rect;

  const items = input.items;
  const cellW = variant.layout === "horizontal" ? vmin * 80 : vmin * 60;
  const cellH = variant.layout === "horizontal" ? vmin * 40 : vmin * 48;
  const positions = computePositions(items.length, cellW, cellH);

  const colors = items.map((it) => it.color);
  const gradients = buildGradients(colors, theme.gradientBase);

  return (
    <Scene3D
      perspective={1000}
      transitionDuration={TRANSITION_DURATION}
      easing="easeInOutCubic"
      style={{ background: theme.bg }}
    >
      <Element3D x={-rect.width / 2} y={-rect.height / 2} z={-100} fixed>
        <GradientTransition
          gradient={gradients}
          duration={items.length * STEP_DURATION}
          easing="easeInOutSine"
          style={{ width: rect.width, height: rect.height }}
        />
      </Element3D>

      {items.map((item, i) => {
        const stepId = `item-${i + 1}`;
        const isFirst = i === 0;
        const isLast = i === items.length - 1;

        return (
          <Step
            key={stepId}
            id={stepId}
            duration={STEP_DURATION}
            x={positions[i].x}
            y={positions[i].y}
            z={0}
            rotateX={positions[i].rotateX}
            rotateY={positions[i].rotateY}
            transition={{
              opacity: [isFirst ? 0 : 0.3, 1],
              blur: [isFirst ? 8 : 6, 0],
              duration: 25,
            }}
            exitTransition={{
              opacity: [1, isLast ? 0 : 0.3],
              blur: [0, 6],
              duration: 25,
            }}
          >
            <ItemScale stepId={stepId}>
              <DrawingReveal
                stepId={stepId}
                width={variant.layout === "horizontal" ? vmin * 72 : vmin * 52}
                height={variant.layout === "horizontal" ? vmin * 32 : vmin * 38}
                radius={vmin * 1.5}
                color={item.color}
                vmin={vmin}
                reveal={variant.reveal}
              >
                <MemoContentItem
                  item={item}
                  vmin={vmin}
                  variant={variant}
                  theme={theme}
                />
              </DrawingReveal>
            </ItemScale>
          </Step>
        );
      })}
    </Scene3D>
  );
};
