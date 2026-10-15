import { afterEach, describe, expect, it } from "vitest"

import {
  COLUMN_WIDTH_KEYS,
  readColumnWidth,
  readSourcePreview,
  SOURCE_PREVIEW_KEY,
  writeColumnWidth,
  writeSourcePreview,
} from "./chrome-prefs"

afterEach(() => localStorage.clear())

describe("source preview preferences", () => {
  it("remembers a source per workspace and clears only the closed workspace", () => {
    writeSourcePreview(1, 12)
    writeSourcePreview(2, 24)

    expect(readSourcePreview(1)).toBe(12)
    expect(readSourcePreview(2)).toBe(24)
    writeSourcePreview(1, null)
    expect(readSourcePreview(1)).toBeNull()
    expect(readSourcePreview(2)).toBe(24)
  })

  it("ignores invalid persisted values", () => {
    localStorage.setItem(SOURCE_PREVIEW_KEY, '{"1":"12","2":-1}')

    expect(readSourcePreview(1)).toBeNull()
    expect(readSourcePreview(2)).toBeNull()
  })
})

describe("column width preferences", () => {
  it("remembers each column's widths apart", () => {
    writeColumnWidth("sidebar", { rest: 320, wide: 640 })
    writeColumnWidth("rightPanel", { rest: 480, wide: 560 })

    expect(readColumnWidth("sidebar")).toEqual({ rest: 320, wide: 640 })
    expect(readColumnWidth("rightPanel")).toEqual({ rest: 480, wide: 560 })
  })

  it("drops a saved width it cannot use", () => {
    localStorage.setItem(COLUMN_WIDTH_KEYS.sidebar, "not json")
    localStorage.setItem(
      COLUMN_WIDTH_KEYS.rightPanel,
      '{"rest":"480","wide":-5}'
    )

    expect(readColumnWidth("sidebar")).toEqual({})
    expect(readColumnWidth("rightPanel")).toEqual({
      rest: undefined,
      wide: undefined,
    })
  })
})
