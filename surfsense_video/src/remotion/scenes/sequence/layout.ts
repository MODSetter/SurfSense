/**
 * Sequence layout utilities — item positioning, connectors, and camera waypoints.
 * Same pattern as list: measure content → position items → build waypoints.
 */
import type { SequenceSceneInput, SequenceItem, LayoutItem, Connector, Waypoint } from "./types";
import type { SequenceLayout } from "./variant";
import { STOP_HOLD, STOP_TRANSITION } from "./constants";
import { measureItemDimensions } from "./components/itemSize";

export interface LayoutParams {
  cardW: number;
  gapX: number;
  gapY: number;
}

interface MeasuredItem {
  data: SequenceItem;
  w: number;
  h: number;
}

/** Measure all items, then position based on actual content size. */
export function positionItems(
  items: SequenceItem[],
  layout: SequenceLayout,
  p: LayoutParams,
  vmin: number,
  showBadge: boolean,
): LayoutItem[] {
  const measured: MeasuredItem[] = items.map((data) => {
    const dims = measureItemDimensions(data, vmin, p.cardW, showBadge);
    return { data, w: dims.width, h: dims.height };
  });

  switch (layout) {
    case "steps":
      return layoutSteps(measured, p);
    case "timeline":
      return layoutTimeline(measured, p);
    case "snake":
      return layoutSnake(measured, p);
    case "ascending":
      return layoutAscending(measured, p);
    case "zigzag":
      return layoutZigzag(measured, p);
  }
}

/** Horizontal row — items side by side with gaps. */
function layoutSteps(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
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

/** Vertical timeline — items stacked with gap. */
function layoutTimeline(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const result: LayoutItem[] = [];
  let y = 0;
  for (let i = 0; i < items.length; i++) {
    const { data, w, h } = items[i];
    result.push({ data, x: 0, y, w, h, index: i });
    y += h + p.gapY;
  }
  return result;
}

/** Snake — items in rows that alternate direction. */
function layoutSnake(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const cols = 3;
  const result: LayoutItem[] = [];

  const rows: MeasuredItem[][] = [];
  for (let i = 0; i < items.length; i += cols) {
    rows.push(items.slice(i, i + cols));
  }

  let y = 0;
  let globalIdx = 0;
  for (let r = 0; r < rows.length; r++) {
    const row = rows[r];
    const reversed = r % 2 === 1;
    const rowH = Math.max(...row.map((it) => it.h));

    for (let c = 0; c < row.length; c++) {
      const colIdx = reversed ? cols - 1 - c : c;
      const { data, w, h } = row[c];
      const x = colIdx * (p.cardW + p.gapX);
      result.push({ data, x, y: y + (rowH - h) / 2, w, h, index: globalIdx });
      globalIdx++;
    }

    y += rowH + p.gapY;
  }

  return result;
}

/** Ascending staircase — each step offset diagonally, no overlap. */
function layoutAscending(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const result: LayoutItem[] = [];
  const n = items.length;
  const stepX = p.cardW + p.gapX;
  const maxH = Math.max(...items.map((it) => it.h));
  const stepY = maxH + p.gapY;

  for (let i = 0; i < n; i++) {
    const { data, w, h } = items[i];
    const x = i * stepX;
    const y = (n - 1 - i) * stepY;
    result.push({ data, x, y, w, h, index: i });
  }

  return result;
}

/** Horizontal zigzag — items alternate between high and low vertical positions. */
function layoutZigzag(items: MeasuredItem[], p: LayoutParams): LayoutItem[] {
  const result: LayoutItem[] = [];
  const maxH = Math.max(...items.map((it) => it.h));
  const levelOffset = maxH + p.gapY;
  const stepX = p.cardW + p.gapX;

  for (let i = 0; i < items.length; i++) {
    const { data, w, h } = items[i];
    const x = i * stepX;
    const isOdd = i % 2 === 1;
    const baseY = isOdd ? levelOffset : 0;
    result.push({ data, x, y: baseY + (maxH - h) / 2, w, h, index: i });
  }

  return result;
}

/** Build connectors between consecutive items. */
export function buildConnectors(
  items: LayoutItem[],
  layout: SequenceLayout,
  vmin: number,
): Connector[] {
  const connectors: Connector[] = [];

  for (let i = 0; i < items.length - 1; i++) {
    const from = items[i];
    const to = items[i + 1];

    let fromX: number, fromY: number, toX: number, toY: number;
    let curvePath: string | undefined;

    if (layout === "steps") {
      fromX = from.x + from.w;
      fromY = from.y + from.h / 2;
      toX = to.x;
      toY = to.y + to.h / 2;
      const pull = Math.abs(toX - fromX) * 0.4;
      curvePath = `M ${fromX} ${fromY} C ${fromX + pull} ${fromY}, ${toX - pull} ${toY}, ${toX} ${toY}`;
    } else if (layout === "timeline") {
      fromX = from.x + from.w / 2;
      fromY = from.y + from.h;
      toX = to.x + to.w / 2;
      toY = to.y;
      const pull = Math.abs(toY - fromY) * 0.4;
      curvePath = `M ${fromX} ${fromY} C ${fromX} ${fromY + pull}, ${toX} ${toY - pull}, ${toX} ${toY}`;
    } else if (layout === "snake") {
      const cols = 3;
      const fromRow = Math.floor(i / cols);
      const toRow = Math.floor((i + 1) / cols);

      if (fromRow === toRow) {
        const reversed = fromRow % 2 === 1;
        if (reversed) {
          fromX = from.x;
          fromY = from.y + from.h / 2;
          toX = to.x + to.w;
          toY = to.y + to.h / 2;
        } else {
          fromX = from.x + from.w;
          fromY = from.y + from.h / 2;
          toX = to.x;
          toY = to.y + to.h / 2;
        }
        const pull = Math.abs(toX - fromX) * 0.4;
        const dir = toX > fromX ? 1 : -1;
        curvePath = `M ${fromX} ${fromY} C ${fromX + dir * pull} ${fromY}, ${toX - dir * pull} ${toY}, ${toX} ${toY}`;
      } else {
        const reversed = fromRow % 2 === 1;
        if (reversed) {
          fromX = from.x;
          fromY = from.y + from.h / 2;
          toX = to.x;
          toY = to.y + to.h / 2;
          const cx = Math.min(fromX, toX) - vmin * 6;
          curvePath = `M ${fromX} ${fromY} C ${cx} ${fromY}, ${cx} ${toY}, ${toX} ${toY}`;
        } else {
          fromX = from.x + from.w;
          fromY = from.y + from.h / 2;
          toX = to.x + to.w;
          toY = to.y + to.h / 2;
          const cx = Math.max(fromX, toX) + vmin * 6;
          curvePath = `M ${fromX} ${fromY} C ${cx} ${fromY}, ${cx} ${toY}, ${toX} ${toY}`;
        }
      }
    } else if (layout === "zigzag") {
      fromX = from.x + from.w;
      fromY = from.y + from.h / 2;
      toX = to.x;
      toY = to.y + to.h / 2;
      const midX = (fromX + toX) / 2;
      curvePath = `M ${fromX} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${toX} ${toY}`;
    } else {
      fromX = from.x + from.w;
      fromY = from.y + from.h / 2;
      toX = to.x;
      toY = to.y + to.h / 2;
      const pull = Math.abs(toX - fromX) * 0.4;
      curvePath = `M ${fromX} ${fromY} C ${fromX + pull} ${fromY}, ${toX - pull} ${toY}, ${toX} ${toY}`;
    }

    connectors.push({ fromX, fromY, toX, toY, curvePath, index: i });
  }

  return connectors;
}

/**
 * Build snap-hold camera waypoints.
 * Groups items that fit within 80% of the viewport, then centers camera on each group.
 */
export function buildWaypoints(
  items: LayoutItem[],
  layout: SequenceLayout,
  viewW: number,
  viewH: number,
): Waypoint[] {
  if (items.length === 0) {
    return [{ cx: 0, cy: 0, holdFrames: STOP_HOLD, transitionAfter: 0 }];
  }

  const usableW = viewW * 0.8;
  const usableH = viewH * 0.8;

  if (layout === "snake" || layout === "ascending") {
    return build2DWaypoints(items, usableW, usableH);
  }

  const isHoriz = layout === "steps" || layout === "zigzag";
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

function build2DWaypoints(
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

/** Compute total scene duration for a sequence input. */
export function sequenceSceneDuration(
  input: SequenceSceneInput,
  layout: SequenceLayout,
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
    gapX: vmin * 8,
    gapY: vmin * 6,
  };
}
