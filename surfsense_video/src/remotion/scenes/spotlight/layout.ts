/**
 * Spotlight scene layout — positions cards and generates one waypoint per card.
 * Each card gets full-viewport treatment; the camera steps between them.
 */
import type { Waypoint } from "./types";
import { STOP_HOLD, STOP_TRANSITION } from "./constants";

export interface CardPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function computeSpotlightLayout(
  count: number,
  viewW: number,
  viewH: number,
): { cards: CardPosition[]; waypoints: Waypoint[] } {
  const vmin = Math.min(viewW, viewH) / 100;
  const cardW = vmin * 60;
  const cardH = vmin * 45;

  const cards: CardPosition[] = [];
  const waypoints: Waypoint[] = [];

  const xOffsets = [0, 0.15, -0.15, 0.1, -0.1, 0.12, -0.12, 0.08];

  for (let i = 0; i < count; i++) {
    const xShift = count > 1 ? viewW * (xOffsets[i % xOffsets.length]) : 0;
    const cx = viewW / 2 + xShift;
    const cy = viewH / 2 + i * viewH;

    cards.push({
      x: cx - cardW / 2,
      y: cy - cardH / 2,
      w: cardW,
      h: cardH,
    });

    waypoints.push({
      cx,
      cy,
      holdFrames: STOP_HOLD,
      transitionAfter: i < count - 1 ? STOP_TRANSITION : 0,
    });
  }

  return { cards, waypoints };
}

export function waypointsDuration(waypoints: Waypoint[]): number {
  let total = 0;
  for (const wp of waypoints) total += wp.holdFrames + wp.transitionAfter;
  return Math.max(1, total);
}

export function spotlightSceneDuration(
  itemCount: number,
  viewW: number,
  viewH: number,
): number {
  const { waypoints } = computeSpotlightLayout(itemCount, viewW, viewH);
  return waypointsDuration(waypoints);
}
