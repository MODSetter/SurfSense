import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { buttonVariants } from "@/components/ui/button"
import { render } from "@/test-utils"

import { TrialButton } from "./trial-button"

function stubBridge(version?: string) {
  const openExternal = vi.fn<(url: string) => Promise<void>>(
    async () => undefined
  )
  window.surfsense = {
    ...window.surfsense!,
    openExternal,
    ...(version
      ? {
          about: {
            details: async () => ({
              version,
              electron: "1",
              chrome: "1",
              node: "1",
              os: "test",
              arch: "x64",
            }),
          },
        }
      : {}),
  }
  return openExternal
}

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("trial button", () => {
  it("opens pricing in the browser from Settings, in its own words", async () => {
    const openExternal = stubBridge()
    const user = userEvent.setup()
    render(<TrialButton />)

    const link = screen.getByRole("link", { name: "Start a free trial" })
    expect(link.className).toBe(buttonVariants())
    await user.click(link)

    expect(openExternal).toHaveBeenCalledWith(
      "https://www.surfsense.com/pricing?utm_source=desktop&utm_medium=app&utm_content=license_trial"
    )
  })

  it("opens the downloads page from a job, in the caller’s words and size", async () => {
    const openExternal = stubBridge("2.3.1")
    const user = userEvent.setup()
    render(
      <TrialButton
        surface="jobs_trial"
        label="Start 14-day trial"
        variant="outline"
        size="sm"
      />
    )

    const link = await screen.findByRole("link", {
      name: "Start 14-day trial",
    })
    expect(link.className).toBe(
      buttonVariants({ variant: "outline", size: "sm" })
    )
    // The version arrives from the bridge after the first render.
    await vi.waitFor(() =>
      expect(link.getAttribute("href")).toContain("app_version=2.3.1")
    )
    await user.click(link)

    expect(openExternal).toHaveBeenCalledWith(
      "https://www.surfsense.com/downloads?utm_source=desktop&utm_medium=app&utm_content=jobs_trial&app_version=2.3.1"
    )
  })
})
