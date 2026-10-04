import { cleanup, screen } from "@testing-library/react"
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

    render(<LiveResourceUsage />)

    expect(await screen.findByRole("meter", { name: "RAM" })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith("/system/usage", expect.anything())
  })

  it("shows a body it cannot read as unavailable instead of breaking the page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )

    render(<LiveResourceUsage />)

    expect(await screen.findByText("Usage unavailable")).toBeTruthy()
  })
})
