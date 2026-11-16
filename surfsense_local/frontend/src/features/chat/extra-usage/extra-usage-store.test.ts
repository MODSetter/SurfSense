import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { extraUsage, notePlanUsage } from "./extra-usage-store"

// 17 Oct 2026, 14:00 UTC, in Unix seconds.
const RESETS_AT = 1792245600

describe("extra usage", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-10-17T12:00:00Z"))
  })
  afterEach(() => {
    notePlanUsage({ using: false, resets_at: null })
    vi.useRealTimers()
  })

  it("holds until when the plan resets, once a reply runs on extra usage", () => {
    notePlanUsage({ using: true, resets_at: RESETS_AT })

    expect(extraUsage()?.resetsAt).toEqual(new Date("2026-10-17T14:00:00Z"))
  })

  it("ends once a reply comes back within the plan", () => {
    notePlanUsage({ using: true, resets_at: RESETS_AT })

    notePlanUsage({ using: false, resets_at: RESETS_AT })

    expect(extraUsage()).toBeNull()
  })

  it("ends on its own when the plan resets", () => {
    notePlanUsage({ using: true, resets_at: RESETS_AT })

    vi.advanceTimersByTime(2 * 60 * 60 * 1000 + 1)

    expect(extraUsage()).toBeNull()
  })

  it("holds with no end when the plan does not say when it resets", () => {
    notePlanUsage({ using: true, resets_at: null })

    expect(extraUsage()).toEqual({ resetsAt: null })
  })
})
