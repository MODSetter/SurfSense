import { cleanup, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"

import { LiveResourceUsage } from "./live-resource-usage"

const USAGE = {
  cpu: { percent: 20, app_percent: 5 },
  memory: {
    total_bytes: 16 * 1024 ** 3,
    used_bytes: 8 * 1024 ** 3,
    app_bytes: 1024 ** 3,
  },
  gpus: [],
  engines: [],
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("live resource usage", () => {
  it("reads the API's usage into the panel", async () => {
    const fetchMock = vi.fn(async () => Response.json(USAGE))
    vi.stubGlobal("fetch", fetchMock)

    render(<LiveResourceUsage shown />)

    expect(await screen.findByRole("meter", { name: "RAM" })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith("/system/usage", expect.anything())
  })

  it("shows a body it cannot read as unavailable instead of breaking the page", async () => {
    // It sits above Studio on every workspace, so it must fail on its own.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )

    render(<LiveResourceUsage shown />)

    expect(await screen.findByText("Usage unavailable")).toBeTruthy()
  })

  it("polls only once the right panel is open", async () => {
    const fetchMock = vi.fn(async () => Response.json(USAGE))
    vi.stubGlobal("fetch", fetchMock)

    const view = render(<LiveResourceUsage shown={false} />)
    // Long enough for an enabled query to have fetched.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(fetchMock).not.toHaveBeenCalled()

    view.rerender(<LiveResourceUsage shown />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  })
})
