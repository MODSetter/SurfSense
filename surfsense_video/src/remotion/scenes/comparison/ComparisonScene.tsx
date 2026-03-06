/**
 * ComparisonScene — renders groups side-by-side in binary or table layout
 * with staggered reveals, animated dividers, and camera paging.
 */
import React, { useMemo } from "react";
import { AbsoluteFill, useVideoConfig, useCurrentFrame, Easing } from "remotion";
import type { ThemeColors } from "../../theme";
import type { ComparisonSceneInput, Waypoint } from "./types";
import type { ComparisonVariant } from "./variant";
import { ITEM_STAGGER, GROUP_STAGGER } from "./constants";
import { CompareCard } from "./components/CompareCard";
import { GroupHeader } from "./components/GroupHeader";
import { CompareDivider } from "./components/Divider";
import { computeComparisonLayout, buildWaypoints } from "./layout";

const DEFAULT_COLORS = ["#6c7dff", "#00c9a7", "#ff6b6b", "#ffd93d"];

interface ComparisonSceneProps {
  input: ComparisonSceneInput;
  theme: ThemeColors;
  variant: ComparisonVariant;
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

export const ComparisonScene: React.FC<ComparisonSceneProps> = ({
  input,
  theme,
  variant,
}) => {
  const { width, height } = useVideoConfig();
  const vmin = Math.min(width, height) / 100;
  const frame = useCurrentFrame();

  const titleOffset = input.title ? vmin * 12 : 0;

  const { layoutResult, waypoints } = useMemo(() => {
    const lr = computeComparisonLayout(input, variant.layout, vmin);
    const wps = buildWaypoints(lr.contentW, lr.contentH, width, height, titleOffset);
    return { layoutResult: lr, waypoints: wps };
  }, [input, variant.layout, vmin, width, height, titleOffset]);

  const cam = resolveCamera(waypoints, frame);
  const panX = width / 2 - cam.cx;
  const panY = height / 2 - cam.cy;

  const groupColors = input.groups.map(
    (g, i) => g.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length],
  );

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
              fontSize: vmin * 3.5,
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
                fontSize: vmin * 1.8,
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
          left: panX,
          top: panY,
        }}
      >
        {layoutResult.dividers.map((d, i) => (
          <CompareDivider
            key={`div${i}`}
            info={d}
            dividerStyle={variant.divider}
            vmin={vmin}
            theme={theme}
            leftColor={groupColors[0]}
            rightColor={groupColors[1]}
          />
        ))}

        {layoutResult.headers.map((h) => {
          const enterF = h.groupIdx * GROUP_STAGGER;
          const group = input.groups[h.groupIdx];
          if (!group || !group.label) return null;
          return (
            <div
              key={`hdr${h.groupIdx}`}
              style={{ position: "absolute", left: h.x, top: h.y }}
            >
              <GroupHeader
                label={group.label}
                color={groupColors[h.groupIdx]}
                enterFrame={enterF}
                vmin={vmin}
                w={h.w}
                h={h.h}
                theme={theme}
              />
            </div>
          );
        })}

        {layoutResult.items.map((it) => {
          const group = input.groups[it.groupIdx];
          if (!group) return null;
          const item = group.items[it.itemIdx];
          if (!item) return null;

          let globalIdx = 0;
          for (let g = 0; g < it.groupIdx; g++) {
            globalIdx += input.groups[g].items.length;
          }
          globalIdx += it.itemIdx;

          const enterF = it.groupIdx * GROUP_STAGGER + globalIdx * ITEM_STAGGER;

          return (
            <div
              key={`item${it.groupIdx}-${it.itemIdx}`}
              style={{ position: "absolute", left: it.x, top: it.y }}
            >
              <CompareCard
                item={item}
                enterFrame={enterF}
                vmin={vmin}
                w={it.w}
                h={it.h}
                color={groupColors[it.groupIdx]}
                cardStyle={variant.cardStyle}
                theme={theme}
              />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
