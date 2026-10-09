import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useDebouncedValue } from "./use-debounced-value"

describe("useDebouncedValue", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("holds the first value until the delay passes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: "q" } }
    )

    rerender({ value: "qw" })
    expect(result.current).toBe("q")

    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current).toBe("qw")
  })

  it("restarts the delay on every change, so a burst settles once", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: "q" } }
    )

    rerender({ value: "qw" })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    rerender({ value: "qwe" })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current).toBe("q")

    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(result.current).toBe("qwe")
  })
})
