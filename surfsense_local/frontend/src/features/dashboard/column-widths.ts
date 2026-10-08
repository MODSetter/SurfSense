import { DETAIL_RAIL_WIDTH, MAIN_RAIL_WIDTH } from "@/components/ui/slide-rail"

/** The chat's own minimum, which no column may take from it. */
export const CHAT_MIN_WIDTH = 520

/**
 * How wide a column may be dragged. Its minimum is also its default: the
 * width it had before columns could be resized. `wideMax` bounds its wide
 * view, a source preview or an inspected citation or artifact.
 */
export type ColumnLimits = { min: number; max: number; wideMax: number }

export const SIDEBAR_LIMITS: ColumnLimits = { min: 272, max: 560, wideMax: 800 }
export const RIGHT_PANEL_LIMITS: ColumnLimits = {
  min: MAIN_RAIL_WIDTH,
  max: 640,
  wideMax: 800,
}

/** A column's chosen width at rest, and in its wide view. */
export type ColumnWidth = { rest: number; wide: number }

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

export function defaultWidth(limits: ColumnLimits): ColumnWidth {
  return { rest: limits.min, wide: DETAIL_RAIL_WIDTH }
}

/** A saved width inside the column's limits; a missing one is the default. */
export function settleWidth(
  saved: Partial<ColumnWidth>,
  limits: ColumnLimits
): ColumnWidth {
  const fallback = defaultWidth(limits)
  return {
    rest: clamp(saved.rest ?? fallback.rest, limits.min, limits.max),
    wide: clamp(saved.wide ?? fallback.wide, limits.min, limits.wideMax),
  }
}

/** The width a column asks for. Its wide view is never narrower than its rest. */
export function askedWidth(width: ColumnWidth, wide: boolean) {
  return wide ? Math.max(width.wide, width.rest) : width.rest
}

/**
 * The widths the columns get in a section this wide (null before it is
 * measured), so the chat keeps its minimum. The sidebar gives way first, as
 * a widened preview always has; neither goes below its own minimum.
 */
export function fitColumns(
  sectionWidth: number | null,
  sidebar: number,
  rightPanel: number
): { sidebar: number; rightPanel: number } {
  if (sectionWidth === null) return { sidebar, rightPanel }
  let over = sidebar + rightPanel - (sectionWidth - CHAT_MIN_WIDTH)
  const sidebarCut = clamp(over, 0, Math.max(0, sidebar - SIDEBAR_LIMITS.min))
  over -= sidebarCut
  const rightPanelCut = clamp(
    over,
    0,
    Math.max(0, rightPanel - RIGHT_PANEL_LIMITS.min)
  )
  return {
    sidebar: sidebar - sidebarCut,
    rightPanel: rightPanel - rightPanelCut,
  }
}

/**
 * The range a column's edge can be dragged through: its limits, no wider
 * than `room` (what the chat and the other column leave), and always
 * holding the width it is `shown` at.
 */
export function dragRange({
  limits,
  width,
  wide,
  room,
  shown,
}: {
  limits: ColumnLimits
  width: ColumnWidth
  wide: boolean
  room: number | null
  shown: number
}): { min: number; max: number } {
  const floor = wide ? Math.max(limits.min, width.rest) : limits.min
  const ceiling = wide ? limits.wideMax : limits.max
  return {
    min: Math.min(floor, shown),
    max: Math.max(shown, room === null ? ceiling : Math.min(ceiling, room)),
  }
}
