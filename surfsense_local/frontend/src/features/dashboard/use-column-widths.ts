import { useLayoutEffect, useState, type RefObject } from "react"

import {
  readColumnWidth,
  writeColumnWidth,
  type ResizableColumn,
} from "./chrome-prefs"
import {
  askedWidth,
  CHAT_MIN_WIDTH,
  defaultWidth,
  dragRange,
  fitColumns,
  RIGHT_PANEL_LIMITS,
  settleWidth,
  SIDEBAR_LIMITS,
  type ColumnLimits,
  type ColumnWidth,
} from "./column-widths"

const LIMITS: Record<ResizableColumn, ColumnLimits> = {
  sidebar: SIDEBAR_LIMITS,
  rightPanel: RIGHT_PANEL_LIMITS,
}

/**
 * The dashboard's two resizable columns: the widths the user chose, fitted
 * to the section that holds them and the chat, and what each edge needs to
 * drag them.
 */
export function useColumnWidths(
  sectionRef: RefObject<HTMLElement | null>,
  {
    sidebarWide,
    rightPanelOpen,
    rightPanelWide,
  }: {
    // Showing a source preview.
    sidebarWide: boolean
    rightPanelOpen: boolean
    // Showing an inspected citation or artifact.
    rightPanelWide: boolean
  }
) {
  const [sectionWidth, setSectionWidth] = useState<number | null>(null)
  const [widths, setWidths] = useState<Record<ResizableColumn, ColumnWidth>>(
    () => ({
      sidebar: settleWidth(readColumnWidth("sidebar"), SIDEBAR_LIMITS),
      rightPanel: settleWidth(
        readColumnWidth("rightPanel"),
        RIGHT_PANEL_LIMITS
      ),
    })
  )
  const [dragging, setDragging] = useState(false)
  // Saved widths may not fit this window: they settle on the first frame
  // without animating, and only later changes slide.
  const [settled, setSettled] = useState(false)

  useLayoutEffect(() => {
    const section = sectionRef.current
    if (!section) return
    // Zero is a section not laid out, as in tests: leave the widths as asked.
    const measure = (width: number) =>
      setSectionWidth(Math.floor(width) || null)
    measure(section.clientWidth)
    const frame = requestAnimationFrame(() => setSettled(true))
    const observer = new ResizeObserver(([entry]) => {
      if (entry) measure(entry.contentRect.width)
    })
    observer.observe(section)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [sectionRef])

  const wide: Record<ResizableColumn, boolean> = {
    sidebar: sidebarWide,
    rightPanel: rightPanelWide,
  }
  const rightPanelAsked = askedWidth(widths.rightPanel, rightPanelWide)
  const shown = fitColumns(
    sectionWidth,
    askedWidth(widths.sidebar, sidebarWide),
    rightPanelOpen ? rightPanelAsked : 0
  )

  const edge = (column: ResizableColumn, other: number) => {
    // Dragging a wide view resizes it, never the width the column rests at.
    const field = wide[column] ? "wide" : "rest"
    const resize = (width: number) =>
      setWidths((current) => ({
        ...current,
        [column]: { ...current[column], [field]: width },
      }))
    const keep = (width: number) => {
      resize(width)
      writeColumnWidth(column, { ...widths[column], [field]: width })
    }
    return {
      value: shown[column],
      ...dragRange({
        limits: LIMITS[column],
        width: widths[column],
        wide: wide[column],
        room:
          sectionWidth === null ? null : sectionWidth - CHAT_MIN_WIDTH - other,
        shown: shown[column],
      }),
      onValueChange: resize,
      onValueCommitted: keep,
      onReset: () => keep(defaultWidth(LIMITS[column])[field]),
      onDraggingChange: setDragging,
    }
  }

  return {
    // Off while an edge is dragged, so the column follows the pointer.
    animate: settled && !dragging,
    sidebar: {
      width: shown.sidebar,
      edge: edge("sidebar", shown.rightPanel),
    },
    rightPanel: {
      // Closed, the rail keeps the width it will open at.
      width: rightPanelOpen ? shown.rightPanel : rightPanelAsked,
      edge: edge("rightPanel", shown.sidebar),
    },
  }
}
