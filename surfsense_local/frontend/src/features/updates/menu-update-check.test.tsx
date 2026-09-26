import { afterEach, describe, expect, it } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"

import { MenuUpdateCheck } from "./menu-update-check"
import { stubUpdateBridge } from "./stub-bridge"

afterEach(() => {
  cleanup()
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
})
