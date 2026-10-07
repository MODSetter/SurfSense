import { describe, expect, it } from "vitest"

import { DETAIL_RAIL_WIDTH } from "@/components/ui/slide-rail"

import {
  askedWidth,
  dragRange,
  fitColumns,
  RIGHT_PANEL_LIMITS,
  settleWidth,
  SIDEBAR_LIMITS,
} from "./column-widths"

describe("column widths", () => {
  it("starts each column at its minimum and its wide view at the detail width", () => {
    expect(settleWidth({}, SIDEBAR_LIMITS)).toEqual({
      rest: 272,
      wide: DETAIL_RAIL_WIDTH,
    })
    expect(settleWidth({}, RIGHT_PANEL_LIMITS)).toEqual({
      rest: 400,
      wide: DETAIL_RAIL_WIDTH,
    })
  })

  it("pulls a saved width back inside the column's limits", () => {
    expect(settleWidth({ rest: 10, wide: 5000 }, SIDEBAR_LIMITS)).toEqual({
      rest: 272,
      wide: 800,
    })
    expect(settleWidth({ rest: 9000 }, RIGHT_PANEL_LIMITS).rest).toBe(640)
  })

  it("never shows a wide view narrower than the column at rest", () => {
    expect(askedWidth({ rest: 300, wide: 560 }, true)).toBe(560)
    expect(askedWidth({ rest: 520, wide: 400 }, true)).toBe(520)
    expect(askedWidth({ rest: 520, wide: 400 }, false)).toBe(520)
  })

  it("leaves the widths alone before the section is measured, or while they fit", () => {
    expect(fitColumns(null, 560, 640)).toEqual({
      sidebar: 560,
      rightPanel: 640,
    })
    expect(fitColumns(1214, 272, 400)).toEqual({
      sidebar: 272,
      rightPanel: 400,
    })
  })

  it("keeps the chat at 520 px, narrowing the sidebar first and then the right panel", () => {
    // 1214 - 520 leaves 694 for both columns.
    expect(fitColumns(1214, 560, 400)).toEqual({
      sidebar: 294,
      rightPanel: 400,
    })
    expect(fitColumns(1214, 560, 640)).toEqual({
      sidebar: 272,
      rightPanel: 422,
    })
    // Too narrow for both minimums: neither goes below its own.
    expect(fitColumns(1000, 560, 640)).toEqual({
      sidebar: 272,
      rightPanel: 400,
    })
    // A collapsed right panel takes nothing.
    expect(fitColumns(1214, 560, 0)).toEqual({ sidebar: 560, rightPanel: 0 })
  })

  it("lets an edge drag between the column's limits and no further than the room the chat leaves", () => {
    const width = { rest: 300, wide: 560 }
    expect(
      dragRange({
        limits: SIDEBAR_LIMITS,
        width,
        wide: false,
        room: null,
        shown: 300,
      })
    ).toEqual({ min: 272, max: 560 })
    expect(
      dragRange({
        limits: SIDEBAR_LIMITS,
        width,
        wide: false,
        room: 400,
        shown: 300,
      })
    ).toEqual({ min: 272, max: 400 })
    // The wide view drags from the resting width to its own maximum.
    expect(
      dragRange({
        limits: SIDEBAR_LIMITS,
        width,
        wide: true,
        room: 2000,
        shown: 560,
      })
    ).toEqual({ min: 300, max: 800 })
  })
})
