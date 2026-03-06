/**
 * ListScene — items positioned in zigzag, column, row, or pyramid layout
 * with snap-hold camera and staggered reveal.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { ListSceneInput, Waypoint } from "./types";
import type { ListVariant } from "./variant";
import { ITEM_STAGGER } from "./constants";
import { ListItemCard } from "./components/ListItem";
import { positionItems, buildWaypoints, getLayoutParams } from "./layout";

interface ListSceneProps {
  input: ListSceneInput;
  theme: ThemeColors;
  variant: ListVariant;
}

function resolveCamera(waypoints: Waypoint[], frame: number): { cx: number; cy: number } {
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

export const ListScene: React.FC<ListSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const { width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;
  const frame = useCurrentFrame();

  const showBadge = variant.showIndex || input.items.some((it) => it.value !== undefined);

  const { items, waypoints } = useMemo(() => {
    const p = getLayoutParams(vmin);
    const positioned = positionItems(input.items, variant.layout, p, vmin, showBadge);
    const wps = buildWaypoints(positioned, variant.layout, width, height);
    return { items: positioned, waypoints: wps };
  }, [input.items, variant.layout, vmin, width, height, showBadge]);

  const cam = resolveCamera(waypoints, frame);

  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      {input.title && (
        <div
          style={{
            position: "absolute",
            top: vmin * 3,
            left: 0,
            width: "100%",
            textAlign: "center",
            zIndex: 10,
          }}
        >
          <div
            style={{
              color: theme.textPrimary,
              fontSize: vmin * 3,
              fontWeight: 700,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {input.title}
          </div>
          {input.subtitle && (
            <div
              style={{
                color: theme.textSecondary,
                fontSize: vmin * 1.5,
                fontFamily: "Inter, system-ui, sans-serif",
                marginTop: vmin * 0.5,
              }}
            >
              {input.subtitle}
            </div>
          )}
        </div>
      )}

      <div
        style={{
          position: "absolute",
          left: width / 2 - cam.cx,
          top: height / 2 - cam.cy,
        }}
      >
        {items.map((it) => {
          const enterF = it.index * ITEM_STAGGER;
          return (
            <div
              key={it.index}
              style={{
                position: "absolute",
                left: it.x,
                top: it.y,
              }}
            >
              <ListItemCard
                item={it.data}
                index={it.index}
                enterFrame={enterF}
                vmin={vmin}
                variant={variant}
                theme={theme}
                cardWidth={it.w}
                cardHeight={it.h}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
