import { describe, expect, it } from "vitest"
import { renderHook } from "@testing-library/react"

import { useStableCallback } from "./use-stable-callback"

describe("useStableCallback", () => {
  it("keeps one identity and calls the latest callback", () => {
    const { result, rerender } = renderHook(
      ({ add }) => useStableCallback((value: number) => value + add),
      { initialProps: { add: 1 } }
    )
    const first = result.current
    expect(first(1)).toBe(2)

    rerender({ add: 10 })

    expect(result.current).toBe(first)
    expect(first(1)).toBe(11)
  })
})
