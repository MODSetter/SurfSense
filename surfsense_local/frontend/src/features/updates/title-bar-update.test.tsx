import { afterEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { stubPrivacyBridge } from "@/features/privacy-choices/stub-privacy-bridge"
import { render } from "@/test-utils"
import { toast } from "sonner"

import { MenuUpdateCheck } from "./menu-update-check"
import { stubUpdateBridge as stubBridge } from "./stub-bridge"
import { TitleBarUpdate } from "./title-bar-update"
import { UP_TO_DATE_SHOWN_MS } from "./up-to-date-confirmation"

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
  delete window.surfsense
})

describe("the title bar's update pill", () => {
  it.each([
    { status: "idle" },
    { status: "up-to-date" },
    { status: "error", message: "net::ERR_INTERNET_DISCONNECTED" },
  ] as const)(
    "offers a check while there is nothing to install ($status)",
    async (state) => {
      const bridge = stubBridge({ automatic: true, state })
      const user = userEvent.setup()
      render(<TitleBarUpdate />)

      await user.click(
        await screen.findByRole("button", { name: "Check for updates" })
      )

      expect(bridge.calls).toEqual(["check"])
    }
  )

  it("says in the pill, not a toast, when its check found nothing newer", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))

    const pill = screen.getByRole("status", { name: "SurfSense is up to date" })
    expect(pill.textContent).toBe("Up to date")
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("offers a check again once it has said so", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    const button = await screen.findByRole("button", {
      name: "Check for updates",
    })
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] })

    fireEvent.click(button)
    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))
    expect(screen.getByRole("status", { name: "SurfSense is up to date" }))
    act(() => vi.advanceTimersByTime(UP_TO_DATE_SHOWN_MS))

    expect(screen.queryByRole("status")).toBeNull()
    expect(screen.getByRole("button", { name: "Check for updates" }))
  })

  it("says nothing when a check it did not start finds nothing newer", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    await screen.findByRole("button", { name: "Check for updates" })

    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))

    expect(screen.queryByRole("status")).toBeNull()
    expect(screen.getByRole("button", { name: "Check for updates" }))
  })

  it("says when its check failed", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
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

  it("asks once, however often it is clicked while asking", async () => {
    const bridge = stubBridge({ automatic: false, state: { status: "idle" } })
    const user = userEvent.setup()
    render(
      <>
        <TitleBarUpdate />
        <EgressPrompt />
      </>
    )

    await user.dblClick(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    await user.click(await screen.findByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(bridge.calls).toEqual(["automatic:true", "check"])
    )
    // A second prompt would open as the first one closes.
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
  })

  it("answers its check even when the result lands in the same render", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    act(() => {
      bridge.push({ status: "checking" })
      bridge.push({ status: "up-to-date" })
    })

    expect(screen.getByRole("status", { name: "SurfSense is up to date" }))
  })

  it("reports one result once, when the menu checks too", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(
      <>
        <MenuUpdateCheck />
        <TitleBarUpdate />
      </>
    )

    await user.click(
      await screen.findByRole("button", { name: "Check for updates" })
    )
    await act(async () => bridge.checkFromMenu())
    // Both checks ran, so the one result is not just the title bar's alone.
    await waitFor(() => expect(bridge.calls).toEqual(["check", "check"]))
    act(() => bridge.push({ status: "checking" }))
    act(() => bridge.push({ status: "up-to-date" }))

    expect(
      screen.getAllByRole("status", { name: "SurfSense is up to date" })
    ).toHaveLength(1)
  })

  it.each(["policy", "channel"] as const)(
    "keeps no space when updates are locked (%s)",
    async (lockedReason) => {
      stubPrivacyBridge({ updates: { locked: true, lockedReason } })
      const { container } = render(<TitleBarUpdate />)
      // Lets the privacy state's read settle; the query notifies on a timer.
      await act(() => new Promise((settle) => setTimeout(settle, 0)))

      expect(container.childElementCount).toBe(0)
    }
  )

  it("shows a check running, with nothing to click", async () => {
    stubBridge({ automatic: true, state: { status: "checking" } })
    render(<TitleBarUpdate />)

    await screen.findByRole("status", { name: "Checking for updates" })
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("shows a download's progress, and how far it got in its label", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    bridge.push({ status: "downloading", version: "1.0.1", percent: 64 })

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading SurfSense 1.0.1",
    })
    expect(progress.getAttribute("aria-valuenow")).toBe("64")
    expect(progress.textContent).toContain("Downloading 64%")
    // A download runs by itself; there is nothing to click.
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("says only that it is downloading until the size is known", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    render(<TitleBarUpdate />)
    bridge.push({ status: "downloading", version: "1.0.1", percent: null })

    const progress = await screen.findByRole("progressbar", {
      name: "Downloading SurfSense 1.0.1",
    })
    expect(progress.hasAttribute("aria-valuenow")).toBe(false)
    expect(progress.textContent).toContain("Downloading…")
  })

  it("restarts into a downloaded update, once", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)
    bridge.push({ status: "ready", version: "1.0.1" })

    const button = await screen.findByRole("button", {
      name: "Restart to install 1.0.1",
    })
    expect(button.textContent).toContain("Update")
    await user.click(button)

    expect(bridge.calls).toEqual(["install"])
    expect(button.hasAttribute("disabled")).toBe(true)
  })

  it("still restarts into a downloaded update when the lock can't be read", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    window.surfsense!.privacy = {
      getState: () => Promise.reject(new Error("main did not answer")),
      onStateChanged: () => () => {},
    } as unknown as NonNullable<typeof window.surfsense>["privacy"]
    render(<TitleBarUpdate />)
    await act(() => new Promise((settle) => setTimeout(settle, 0)))
    // Unknown whether checks are locked, so no check is offered.
    expect(
      screen.queryByRole("button", { name: "Check for updates" })
    ).toBeNull()

    act(() => bridge.push({ status: "ready", version: "1.0.1" }))

    await screen.findByRole("button", { name: "Restart to install 1.0.1" })
  })

  it("says what it does in its own label, with no tooltip", async () => {
    const bridge = stubBridge({ automatic: true, state: { status: "idle" } })
    const user = userEvent.setup()
    render(<TitleBarUpdate />)
    bridge.push({ status: "ready", version: "1.0.1" })

    await user.hover(
      await screen.findByRole("button", { name: "Restart to install 1.0.1" })
    )

    expect(screen.queryByRole("tooltip")).toBeNull()
  })
})

describe(
  "the title bar's update pill in the Docker image",
  {
    tags: ["docker"],
  },
  () => {
    it("keeps no space, since there is no updater to check", async () => {
      const { container } = render(<TitleBarUpdate />)
      await act(() => new Promise((settle) => setTimeout(settle, 0)))

      expect(container.childElementCount).toBe(0)
    })
  }
)
