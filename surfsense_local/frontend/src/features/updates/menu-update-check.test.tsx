import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"
import { toast } from "sonner"

import { MenuUpdateCheck } from "./menu-update-check"
import { stubUpdateBridge } from "./stub-bridge"

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  delete window.surfsense
})

function renderMenuCheck() {
  render(
    <>
      <MenuUpdateCheck />
      <EgressPrompt />
    </>
  )
}

describe("Check for Updates… in the app menu", () => {
  it("checks straight away once update checks are allowed", async () => {
    const bridge = stubUpdateBridge({
      automatic: true,
      state: { status: "idle" },
    })
    renderMenuCheck()

    await act(async () => bridge.checkFromMenu())

    await waitFor(() => expect(bridge.calls).toEqual(["check"]))
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("asks first while they are off, and only that", async () => {
    const bridge = stubUpdateBridge({
      automatic: false,
      state: { status: "idle" },
    })
    const user = userEvent.setup()
    renderMenuCheck()

    await act(async () => bridge.checkFromMenu())

    await screen.findByRole("alertdialog", {
      name: "Allow SurfSense to check for updates?",
    })
    expect(bridge.calls).toEqual([])

    await user.click(screen.getByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(bridge.calls).toEqual(["automatic:true", "check"])
    )
  })

  it("says when there is nothing newer, since nothing else would", async () => {
    const bridge = stubUpdateBridge({
      automatic: true,
      // A result from an earlier check must not answer this one.
      state: { status: "up-to-date" },
    })
    renderMenuCheck()

    await act(async () => bridge.checkFromMenu())
    expect(toast.success).not.toHaveBeenCalled()
    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))

    expect(toast.success).toHaveBeenCalledWith("SurfSense is up to date")
  })

  it("says when the check failed", async () => {
    const bridge = stubUpdateBridge({
      automatic: true,
      state: { status: "idle" },
    })
    renderMenuCheck()

    await act(async () => bridge.checkFromMenu())
    act(() => bridge.push({ status: "checking" }))
    act(() =>
      bridge.push({
        status: "error",
        message: "net::ERR_INTERNET_DISCONNECTED",
      })
    )

    expect(toast.error).toHaveBeenCalledWith("Couldn’t check for updates", {
      description: "net::ERR_INTERNET_DISCONNECTED",
    })
  })

  it("leaves a found update to the title bar", async () => {
    const bridge = stubUpdateBridge({
      automatic: true,
      state: { status: "idle" },
    })
    renderMenuCheck()

    await act(async () => bridge.checkFromMenu())
    act(() => bridge.push({ status: "checking" }))
    act(() =>
      bridge.push({ status: "downloading", version: "1.0.1", percent: null })
    )
    act(() => bridge.push({ status: "up-to-date" }))

    expect(toast.success).not.toHaveBeenCalled()
  })

  it("stays quiet for a check it did not start", () => {
    const bridge = stubUpdateBridge({
      automatic: true,
      state: { status: "idle" },
    })
    renderMenuCheck()

    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))

    expect(toast.success).not.toHaveBeenCalled()
  })
})
