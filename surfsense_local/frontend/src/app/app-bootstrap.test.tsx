import { act, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import { AppBootstrap } from "./app-bootstrap"

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("app bootstrap", () => {
  it("shows an animated ASCII loader while startup is pending", () => {
    vi.useFakeTimers()
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))

    render(<AppBootstrap />)

    expect(screen.getByRole("status", { name: "Starting SurfSense" })).toHaveTextContent(
      "[|]"
    )
    act(() => vi.advanceTimersByTime(120))
    expect(screen.getByRole("status")).toHaveTextContent("[/]")
  })
})
