/**
 * List layout utilities — item positioning and camera waypoints.
 * Item heights are measured via canvas.measureText before positioning,
 * so layout adapts to actual content (same approach as hierarchy scene).
 */
import type { ListSceneInput, ListItem, LayoutItem, Waypoint } from "./types";
import type { ListLayout } from "./variant";
import { STOP_HOLD, STOP_TRANSITION } from "./constants";
import { measureItemDimensions } from "./components/itemSize";

export interface LayoutParams {
  cardW: number;
  gapX: number;
  gapY: number;
}

interface MeasuredItem {
  data: ListItem;
  w: number;
  h: number;
}

/** Measure all items, then position based on actual content size. */
export function positionItems(
  items: ListItem[],
  layout: ListLayout,
  p: LayoutParams,
  vmin: number,
  showBadge: boolean,
): LayoutItem[] {
  const measured: MeasuredItem[] = items.map((data) => {
    const dims = measureItemDimensions(data, vmin, p.cardW, showBadge);
    return { data, w: dims.width, h: dims.height };
  });

  switch (layout) {
    case "column":
      return layoutColumn(measured, p);

    case "row":
      return layoutRow(measured, p);

    case "zigzag":
      return layoutZigzag(measured, p);

    case "pyramid":
      return layoutPyramid(measured, p);
  }
}

function layoutColumn(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const result: LayoutItem[] = [];
  let y = 0;
  for (let i = 0; i < items.length; i++) {
    const { data, w, h } = items[i];
    result.push({ data, x: 0, y, w, h, index: i });
    y += h + p.gapY;
  }
  return result;
}

function layoutRow(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const maxH = Math.max(...items.map((it) => it.h));
  const result: LayoutItem[] = [];
  let x = 0;
  for (let i = 0; i < items.length; i++) {
    const { data, w, h } = items[i];
    result.push({ data, x, y: (maxH - h) / 2, w, h, index: i });
    x += w + p.gapX;
  }
  return result;
}

function layoutZigzag(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const offset = p.cardW * 0.6;
  const result: LayoutItem[] = [];
  let y = 0;
  for (let i = 0; i < items.length; i++) {
    const { data, w, h } = items[i];
    result.push({ data, x: i % 2 === 0 ? 0 : offset, y, w, h, index: i });
    y += h + p.gapY;
  }
  return result;
}

function layoutPyramid(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const levels: number[] = [];
  let remaining = items.length;
  for (let level = 0; remaining > 0; level++) {
    const count = Math.min(level + 1, remaining);
    levels.push(count);
    remaining -= count;
  }

  const maxLevelSize = Math.max(...levels);
  const maxLevelW = maxLevelSize * items[0].w + (maxLevelSize - 1) * p.gapX;
  const centerX = maxLevelW / 2;

  const result: LayoutItem[] = [];
  let itemIdx = 0;
  let y = 0;

  for (const levelSize of levels) {
    const rowItems = items.slice(itemIdx, itemIdx + levelSize);
    const rowH = Math.max(...rowItems.map((it) => it.h));
    const totalW = levelSize * rowItems[0].w + (levelSize - 1) * p.gapX;
    const startX = centerX - totalW / 2;

    for (let i = 0; i < levelSize; i++) {
      const { data, w, h } = rowItems[i];
      result.push({
        data,
        x: startX + i * (w + p.gapX),
        y: y + (rowH - h) / 2,
        w,
        h,
        index: itemIdx + i,
      });
    }

    y += rowH + p.gapY;
    itemIdx += levelSize;
  }

  return result;
}

/**
 * Build snap-hold camera waypoints.
 * cx/cy = world-space center point the viewport looks at.
 * Scene renders container at: left = viewW/2 - cx, top = viewH/2 - cy.
 */
export function buildWaypoints(
  items: LayoutItem[],
  layout: ListLayout,
  viewW: number,
  viewH: number,
): Waypoint[] {
  if (items.length === 0) {
    return [{ cx: 0, cy: 0, holdFrames: STOP_HOLD, transitionAfter: 0 }];
  }

  const usableW = viewW * 0.8;
  const usableH = viewH * 0.8;

  if (layout === "pyramid") {
    return buildPyramidWaypoints(items, usableW, usableH);
  }

  const isHoriz = layout === "row";
  const primaryAxis = isHoriz ? "x" : "y";
  const primarySize = isHoriz ? "w" : "h";
  const usable = isHoriz ? usableW : usableH;

  const sorted = [...items].sort((a, b) => a[primaryAxis] - b[primaryAxis]);
  const stops: Waypoint[] = [];
  let i = 0;

  while (i < sorted.length) {
    const anchor = sorted[i][primaryAxis];
    let lastIdx = i;
    while (
      lastIdx + 1 < sorted.length &&
      sorted[lastIdx + 1][primaryAxis] +
        sorted[lastIdx + 1][primarySize] -
        anchor <=
        usable
    ) {
      lastIdx++;
    }

    const group = sorted.slice(i, lastIdx + 1);
    const bbox = groupBBox(group);

    stops.push({
      cx: (bbox.minX + bbox.maxX) / 2,
      cy: (bbox.minY + bbox.maxY) / 2,
      holdFrames: STOP_HOLD,
      transitionAfter: STOP_TRANSITION,
    });
    i = lastIdx + 1;
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

/**
 * Pyramid spreads in 2D — group items into viewport-sized windows,
 * first by rows (vertical bands) that fit usableH, then within each
 * band split horizontally if the level is wider than usableW.
 */
function buildPyramidWaypoints(
  items: LayoutItem[],
  usableW: number,
  usableH: number,
): Waypoint[] {
  const sorted = [...items].sort((a, b) => a.y - b.y || a.x - b.x);
  const stops: Waypoint[] = [];

  let i = 0;
  while (i < sorted.length) {
    const anchorY = sorted[i].y;
    let lastRow = i;
    while (
      lastRow + 1 < sorted.length &&
      sorted[lastRow + 1].y + sorted[lastRow + 1].h - anchorY <= usableH
    ) {
      lastRow++;
    }

    const rowBand = sorted.slice(i, lastRow + 1);

    const rowSorted = [...rowBand].sort((a, b) => a.x - b.x);
    let j = 0;
    while (j < rowSorted.length) {
      const anchorX = rowSorted[j].x;
      let lastCol = j;
      while (
        lastCol + 1 < rowSorted.length &&
        rowSorted[lastCol + 1].x + rowSorted[lastCol + 1].w - anchorX <= usableW
      ) {
        lastCol++;
      }

      const group = rowSorted.slice(j, lastCol + 1);
      const bbox = groupBBox(group);
      stops.push({
        cx: (bbox.minX + bbox.maxX) / 2,
        cy: (bbox.minY + bbox.maxY) / 2,
        holdFrames: STOP_HOLD,
        transitionAfter: STOP_TRANSITION,
      });
      j = lastCol + 1;
    }

    i = lastRow + 1;
  }

  if (stops.length > 0) stops[stops.length - 1].transitionAfter = 0;
  return stops;
}

function groupBBox(items: LayoutItem[]) {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const it of items) {
    minX = Math.min(minX, it.x);
    minY = Math.min(minY, it.y);
    maxX = Math.max(maxX, it.x + it.w);
    maxY = Math.max(maxY, it.y + it.h);
  }
  return { minX, minY, maxX, maxY };
}

/** Total duration from waypoints. */
export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) {
    total += wp.holdFrames + wp.transitionAfter;
  }
  return Math.max(1, total);
}

/** Compute total scene duration for a list input. */
export function listSceneDuration(
  input: ListSceneInput,
  layout: ListLayout,
  viewW: number,
  viewH: number,
  showBadge = true,
): number {
  const vmin = Math.min(viewW, viewH) / 100;
  const p = getLayoutParams(vmin);
  const positioned = positionItems(input.items, layout, p, vmin, showBadge);
  const wps = buildWaypoints(positioned, layout, viewW, viewH);
  return waypointsDuration(wps);
}

export function getLayoutParams(vmin: number): LayoutParams {
  return {
    cardW: vmin * 45,
    gapX: vmin * 4,
    gapY: vmin * 3,
  };
}
