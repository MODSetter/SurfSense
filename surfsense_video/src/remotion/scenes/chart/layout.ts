/** Chart scene layout utilities — bar/line sizing, camera waypoints, duration. */
import { ITEM_STAGGER, ITEM_ANIM_DURATION, HOLD_AFTER } from "./constants";
import type { ChartLayout } from "./variant";

export interface Waypoint {
  cx: number;
  cy: number;
  holdFrames: number;
  transitionAfter: number;
}

const STOP_HOLD = 120;
const STOP_TRANSITION = 18;

/* ─── Bar / Column layout ─── */

export interface BarLayoutInfo {
  barThickness: number;
  gap: number;
  totalSize: number;
  overflow: boolean;
}

export function computeBarLayout(
  itemCount: number,
  availableSize: number,
  vmin: number,
): BarLayoutInfo {
  const gap = vmin * 1.2;
  const minThickness = vmin * 4;
  const maxThickness = vmin * 6;
  const totalGaps = (itemCount - 1) * gap;
  const rawThickness = (availableSize - totalGaps) / itemCount;
  const barThickness = Math.max(minThickness, Math.min(rawThickness, maxThickness));
  const totalSize = itemCount * barThickness + totalGaps;
  const overflow = totalSize > availableSize;

  return { barThickness, gap, totalSize, overflow };
}

export function buildBarWaypoints(
  itemCount: number,
  barLayout: BarLayoutInfo,
  viewSize: number,
  isColumn: boolean,
): Waypoint[] {
  if (!barLayout.overflow) {
    const center = barLayout.totalSize / 2;
    return [{
      cx: isColumn ? center : 0,
      cy: isColumn ? 0 : center,
      holdFrames: STOP_HOLD,
      transitionAfter: 0,
    }];
  }

  const usable = viewSize * 0.85;
  const { barThickness, gap } = barLayout;
  const step = barThickness + gap;

  const stops: Waypoint[] = [];
  let i = 0;

  while (i < itemCount) {
    const startPos = i * step;
    let lastIdx = i;

    while (
      lastIdx + 1 < itemCount &&
      (lastIdx + 1) * step + barThickness - startPos <= usable
    ) {
      lastIdx++;
    }

    const groupEnd = lastIdx * step + barThickness;
    const center = (startPos + groupEnd) / 2;

    stops.push({
      cx: isColumn ? center : 0,
      cy: isColumn ? 0 : center,
      holdFrames: STOP_HOLD,
      transitionAfter: STOP_TRANSITION,
    });

    i = lastIdx + 1;
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

/* ─── Line chart layout ─── */

export interface LineLayoutInfo {
  totalW: number;
  pointSpacing: number;
  overflow: boolean;
}

export function computeLineLayout(
  itemCount: number,
  availableW: number,
  vmin: number,
): LineLayoutInfo {
  const minSpacing = vmin * 8;
  const naturalSpacing = availableW / Math.max(itemCount - 1, 1);

  if (naturalSpacing >= minSpacing) {
    return { totalW: availableW, pointSpacing: naturalSpacing, overflow: false };
  }

  const totalW = (itemCount - 1) * minSpacing;
  return { totalW, pointSpacing: minSpacing, overflow: true };
}

export function buildLineWaypoints(
  lineLayout: LineLayoutInfo,
  viewW: number,
): Waypoint[] {
  if (!lineLayout.overflow) {
    return [{
      cx: lineLayout.totalW / 2,
      cy: 0,
      holdFrames: STOP_HOLD,
      transitionAfter: 0,
    }];
  }

  const usable = viewW * 0.85;
  const stops: Waypoint[] = [];
  let pos = 0;

  while (pos < lineLayout.totalW) {
    const windowEnd = Math.min(pos + usable, lineLayout.totalW);
    const center = (pos + windowEnd) / 2;

    stops.push({
      cx: center,
      cy: 0,
      holdFrames: STOP_HOLD,
      transitionAfter: STOP_TRANSITION,
    });

    if (windowEnd >= lineLayout.totalW) break;
    pos = windowEnd - usable * 0.15;
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

/* ─── Duration helpers ─── */

export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) {
    total += wp.holdFrames + wp.transitionAfter;
  }
  return Math.max(1, total);
}

export function chartSceneDuration(
  itemCount: number,
  layout: ChartLayout,
  viewW: number,
  viewH: number,
  vmin: number,
): number {
  const animPhase = (itemCount - 1) * ITEM_STAGGER + ITEM_ANIM_DURATION;

  if (layout === "bar" || layout === "column") {
    const isCol = layout === "column";
    const availableSize = isCol ? viewW : viewH;
    const barInfo = computeBarLayout(itemCount, availableSize, vmin);

    if (barInfo.overflow) {
      const wps = buildBarWaypoints(itemCount, barInfo, availableSize, isCol);
      return animPhase + waypointsDuration(wps);
    }
  }

  if (layout === "line") {
    const lineInfo = computeLineLayout(itemCount, viewW, vmin);
    if (lineInfo.overflow) {
      const wps = buildLineWaypoints(lineInfo, viewW);
      return animPhase + waypointsDuration(wps);
    }
  }

  return animPhase + HOLD_AFTER;
}
