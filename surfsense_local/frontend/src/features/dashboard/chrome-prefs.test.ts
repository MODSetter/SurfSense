import { afterEach, describe, expect, it } from "vitest"

import {
  readSourcePreview,
  SOURCE_PREVIEW_KEY,
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
