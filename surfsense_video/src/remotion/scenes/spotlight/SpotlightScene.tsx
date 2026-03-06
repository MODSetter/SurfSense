/**
 * SpotlightScene -- shows cards one at a time with full-viewport treatment.
 * Uses the standard camera system (waypoints + eased transitions).
 * Each card gets its own camera stop with a stroke-reveal entrance.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { SpotlightSceneInput, Waypoint } from "./types";
import type { SpotlightVariant } from "./variant";
import { computeSpotlightLayout } from "./layout";
import { SpotlightCard } from "./components/SpotlightCard";
import { STOP_HOLD, STOP_TRANSITION } from "./constants";

interface SpotlightSceneProps {
  input: SpotlightSceneInput;
  theme: ThemeColors;
  variant: SpotlightVariant;
}

function resolveCamera(
  waypoints: Waypoint[],
  frame: number,
): { cx: number; cy: number } {
  let cam = { cx: waypoints[0].cx, cy: waypoints[0].cy };
  let cursor = 0;

  for (let w = 0; w < waypoints.length; w++) {
    const wp = waypoints[w];
    if (frame < cursor + wp.holdFrames) {
      cam = { cx: wp.cx, cy: wp.cy };
      break;
    }
    cursor += wp.holdFrames;

    if (wp.transitionAfter > 0 && w + 1 < waypoints.length) {
      if (frame < cursor + wp.transitionAfter) {
        const t = Easing.inOut(Easing.ease)(
          (frame - cursor) / wp.transitionAfter,
        );
        const next = waypoints[w + 1];
        cam = {
          cx: wp.cx + (next.cx - wp.cx) * t,
          cy: wp.cy + (next.cy - wp.cy) * t,
        };
        break;
      }
      cursor += wp.transitionAfter;
    }

    if (w === waypoints.length - 1) {
      cam = { cx: wp.cx, cy: wp.cy };
    }
  }

  return cam;
}

function getEnterFrame(index: number): number {
  return index * (STOP_HOLD + STOP_TRANSITION);
}

export const SpotlightScene: React.FC<SpotlightSceneProps> = ({
  input, theme, variant,
}) => {
  const { width, height } = useVideoConfig();
  const frame = useCurrentFrame();

  const { cards, waypoints } = useMemo(
    () => computeSpotlightLayout(input.items.length, width, height),
    [input.items.length, width, height],
  );

  const cam = resolveCamera(waypoints, frame);
  const panX = width / 2 - cam.cx;
  const panY = height / 2 - cam.cy;

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: panX, top: panY }}>
        {input.items.map((item, i) => {
          const distY = Math.abs(cards[i].y + cards[i].h / 2 - cam.cy);
          if (distY > height * 1.5) return null;

          return (
            <div
              key={`card-${i}`}
              style={{
                position: "absolute",
                left: cards[i].x,
                top: cards[i].y,
              }}
            >
              <SpotlightCard
                item={item}
                index={i}
                enterFrame={getEnterFrame(i)}
                vmin={Math.min(width, height) / 100}
                w={cards[i].w}
                h={cards[i].h}
                variant={variant}
                theme={theme}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
