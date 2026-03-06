/**
 * Comparison scene layout — binary, table.
 * Computes item positions, group headers, divider, camera waypoints, duration.
 */
import type { ComparisonSceneInput, Waypoint } from "./types";
import type { ComparisonLayout } from "./variant";
import { getMaxItemHeight } from "./components/itemSize";
import {
  ITEM_STAGGER,
  ITEM_FADE_DURATION,
  GROUP_STAGGER,
  STOP_HOLD,
  STOP_TRANSITION,
} from "./constants";

export interface LayoutItem {
  groupIdx: number;
  itemIdx: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LayoutHeader {
  groupIdx: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DividerInfo {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ComparisonLayoutResult {
  items: LayoutItem[];
  headers: LayoutHeader[];
  dividers: DividerInfo[];
  contentW: number;
  contentH: number;
}

/* ─── Binary layout (2 groups, side-by-side with VS divider) ─── */

function layoutBinary(
  input: ComparisonSceneInput,
  vmin: number,
): ComparisonLayoutResult {
  const left = input.groups[0];
  const right = input.groups[1];
  const leftItems = left.items;
  const rightItems = right.items;

  const colW = vmin * 32;
  const rowGap = vmin * 3;
  const headerH = vmin * 7;
  const dividerW = vmin * 10;
  const gap = vmin * 3;

  const allItems = [...leftItems, ...rightItems];
  const rowH = getMaxItemHeight(allItems, vmin, colW);

  const maxRows = Math.max(leftItems.length, rightItems.length);
  const contentH = headerH + maxRows * (rowH + rowGap) - rowGap;
  const contentW = colW + gap + dividerW + gap + colW;

  const leftX = 0;
  const rightX = colW + gap + dividerW + gap;

  const items: LayoutItem[] = [];
  const headers: LayoutHeader[] = [
    { groupIdx: 0, x: leftX, y: 0, w: colW, h: headerH },
    { groupIdx: 1, x: rightX, y: 0, w: colW, h: headerH },
  ];

  leftItems.forEach((_, i) => {
    items.push({
      groupIdx: 0,
      itemIdx: i,
      x: leftX,
      y: headerH + i * (rowH + rowGap),
      w: colW,
      h: rowH,
    });
  });

  rightItems.forEach((_, i) => {
    items.push({
      groupIdx: 1,
      itemIdx: i,
      x: rightX,
      y: headerH + i * (rowH + rowGap),
      w: colW,
      h: rowH,
    });
  });

  const dividers: DividerInfo[] = [
    {
      x: colW + gap,
      y: 0,
      w: dividerW,
      h: contentH,
    },
  ];

  return { items, headers, dividers, contentW, contentH };
}

/* ─── Table layout (N groups as columns, items as rows) ─── */

function layoutTable(
  input: ComparisonSceneInput,
  vmin: number,
): ComparisonLayoutResult {
  const groups = input.groups;
  const colW = vmin * 28;
  const colGap = vmin * 3;
  const rowGap = vmin * 3;
  const headerH = vmin * 7;

  const allItems = groups.flatMap((g) => g.items);
  const rowH = getMaxItemHeight(allItems, vmin, colW);

  const maxRows = Math.max(...groups.map((g) => g.items.length));
  const contentW = groups.length * colW + (groups.length - 1) * colGap;
  const contentH = headerH + maxRows * (rowH + rowGap) - rowGap;

  const items: LayoutItem[] = [];
  const headers: LayoutHeader[] = [];

  groups.forEach((group, gi) => {
    const colX = gi * (colW + colGap);
    headers.push({ groupIdx: gi, x: colX, y: 0, w: colW, h: headerH });

    group.items.forEach((_, ii) => {
      items.push({
        groupIdx: gi,
        itemIdx: ii,
        x: colX,
        y: headerH + ii * (rowH + rowGap),
        w: colW,
        h: rowH,
      });
    });
  });

  return { items, headers, dividers: [], contentW, contentH };
}

/* ─── Camera waypoints ─── */

export function buildWaypoints(
  contentW: number,
  contentH: number,
  viewW: number,
  viewH: number,
  titleOffset: number = 0,
): Waypoint[] {
  const effectiveH = viewH - titleOffset;
  const cx = contentW / 2;
  const cy = contentH / 2 - titleOffset / 2;

  if (contentW <= viewW * 0.85 && contentH <= effectiveH * 0.85) {
    return [{ cx, cy, holdFrames: STOP_HOLD, transitionAfter: 0 }];
  }

  const colsNeeded = contentW > viewW ? Math.ceil(contentW / (viewW * 0.75)) : 1;
  const rowsNeeded = contentH > effectiveH ? Math.ceil(contentH / (effectiveH * 0.75)) : 1;

  const stops: Waypoint[] = [];

  for (let r = 0; r < rowsNeeded; r++) {
    for (let c = 0; c < colsNeeded; c++) {
      const tx = colsNeeded === 1
        ? cx
        : viewW / 2 + (c / (colsNeeded - 1)) * Math.max(0, contentW - viewW);

      let ty: number;
      if (rowsNeeded === 1) {
        ty = cy;
      } else {
        const firstCy = viewH / 2 - titleOffset;
        const lastCy = contentH - viewH / 2;
        ty = firstCy + (r / (rowsNeeded - 1)) * Math.max(0, lastCy - firstCy);
      }

      stops.push({ cx: tx, cy: ty, holdFrames: STOP_HOLD, transitionAfter: STOP_TRANSITION });
    }
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

/* ─── Public API ─── */

export function computeComparisonLayout(
  input: ComparisonSceneInput,
  layout: ComparisonLayout,
  vmin: number,
): ComparisonLayoutResult {
  switch (layout) {
    case "binary":
      return layoutBinary(input, vmin);
    case "table":
      return layoutTable(input, vmin);
  }
}

export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) total += wp.holdFrames + wp.transitionAfter;
  return Math.max(1, total);
}

export function comparisonSceneDuration(
  input: ComparisonSceneInput,
  layout: ComparisonLayout,
  viewW: number,
  viewH: number,
): number {
  const vmin = Math.min(viewW, viewH) / 100;
  const titleOffset = input.title ? vmin * 12 : 0;
  const result = computeComparisonLayout(input, layout, vmin);
  const wps = buildWaypoints(result.contentW, result.contentH, viewW, viewH, titleOffset);
  const totalItems = input.groups.reduce((s, g) => s + g.items.length, 0);
  const animPhase =
    (input.groups.length - 1) * GROUP_STAGGER +
    (totalItems - 1) * ITEM_STAGGER +
    ITEM_FADE_DURATION;
  return animPhase + waypointsDuration(wps);
}
