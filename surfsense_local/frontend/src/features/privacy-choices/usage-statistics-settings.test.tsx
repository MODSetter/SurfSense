import { afterEach, describe, expect, it } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { UpdateSettings } from "@/features/updates/update-settings"
import { render } from "@/test-utils"

import { stubPrivacyBridge } from "./stub-privacy-bridge"
import { UsageStatisticsSettings } from "./usage-statistics-settings"

afterEach(() => {
  cleanup()
  delete window.surfsense
})

const lastSent = {
  at: "2026-10-20T09:00:00Z",
  body: { schema: 1, app_version: "2.2.4", active: { first: true } },
}

describe("usage statistics in Settings › About", () => {
  it("switches usage statistics on and off", async () => {
    const bridge = stubPrivacyBridge()
    const user = userEvent.setup()
    render(<UsageStatisticsSettings />)

    const toggle = await screen.findByRole("switch", {
      name: "Usage statistics",
    })
    // Never asked reads as off, not as a choice made.
    expect(toggle.getAttribute("aria-checked")).toBe("false")
    await user.click(toggle)
    await waitFor(() =>
      expect(toggle.getAttribute("aria-checked")).toBe("true")
    )
    await user.click(toggle)
    await waitFor(() =>
      expect(toggle.getAttribute("aria-checked")).toBe("false")
    )
    expect(bridge.calls).toEqual(["usage:true", "usage:false"])
  })

  it("holds the switch off and says why when a policy forbids it", async () => {
    stubPrivacyBridge({
      usageStatistics: { enabled: false, locked: true, lockedReason: "policy" },
    })
    render(<UsageStatisticsSettings />)

    const toggle = await screen.findByRole("switch", {
      name: "Usage statistics",
    })
    expect(toggle.getAttribute("aria-checked")).toBe("false")
    expect(toggle.hasAttribute("data-disabled")).toBe(true)
    expect(
      screen.getByText(
        "Your organization’s policy turned usage statistics off on this computer."
      )
    ).toBeTruthy()
  })

  it("shows the next report, the last one sent and where it goes", async () => {
    stubPrivacyBridge({ usageStatistics: { enabled: true, lastSent } })
    const user = userEvent.setup()
    render(<UsageStatisticsSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Show exactly what’s sent" })
    )
    const dialog = await screen.findByRole("dialog", {
      name: "What usage statistics send",
    })
    expect(dialog.textContent).toContain("usage.surfsense.com")
    expect(dialog.textContent).toContain(
      "during the install’s first week one more each time setup reaches a new step, at most four more"
    )
    const next = await within(dialog).findByLabelText(
      "The next daily usage report"
    )
    expect(next.textContent).toContain('"app_version": "2.2.4"')
    const sent = within(dialog).getByLabelText("The last usage report sent")
    expect(sent.textContent).toContain('"first": true')
    expect(dialog.textContent).toContain("Sent ")
  })
})

describe("App updates in Settings › About", () => {
  it("shows the last update request with its headers, and its fallback", async () => {
    stubPrivacyBridge({
      updates: {
        automatic: true,
        lastCheckedAt: "2026-10-21T08:00:00Z",
        lastRequest: {
          url: "https://updates.surfsense.com/api/updates/stable.yml",
          headers: {
            "X-SurfSense-Version": "2.2.4",
            "X-SurfSense-Platform": "win32-x64",
            "X-SurfSense-OS": "windows-11",
          },
        },
      },
    })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Show exactly what’s sent" })
    )
    const dialog = await screen.findByRole("dialog", {
      name: "What an update check sends",
    })
    const request = within(dialog).getByLabelText("The last update request")
    expect(request.textContent).toContain(
      "GET https://updates.surfsense.com/api/updates/stable.yml"
    )
    expect(request.textContent).toContain("X-SurfSense-Platform: win32-x64")
    expect(dialog.textContent).toContain("github.com")
  })

  it("names a policy's mirror as the only update host", async () => {
    stubPrivacyBridge({
      updates: { host: "updates.example.org", fallbackHost: null },
    })
    const user = userEvent.setup()
    render(<UpdateSettings />)

    expect(
      await screen.findByText(
        "Checks your organization’s update server once a day. No ID sent."
      )
    ).toBeTruthy()
    await user.hover(
      screen.getByRole("button", { name: "What an update check sends" })
    )
    const details = (await screen.findByRole("tooltip")).textContent
    expect(details).toContain("updates.example.org")
    expect(details).not.toContain("github.com")
  })

  it("says each in one line, with the full description behind the info icon", async () => {
    stubPrivacyBridge()
    const user = userEvent.setup()
    render(
      <>
        <UpdateSettings />
        <UsageStatisticsSettings />
      </>
    )

    expect(
      await screen.findByText(
        "Checks for a newer version once a day. No ID sent."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "A daily count of how SurfSense is used, in ranges, and one more for each setup step in the first week. Never your documents, prompts or an ID."
      )
    ).toBeTruthy()

    await user.hover(
      screen.getByRole("button", { name: "What an update check sends" })
    )
    expect((await screen.findByRole("tooltip")).textContent).toContain(
      "githubusercontent.com"
    )
    await user.unhover(
      screen.getByRole("button", { name: "What an update check sends" })
    )
    await waitFor(() => expect(screen.queryByRole("tooltip")).toBeNull())
    await user.hover(
      screen.getByRole("button", { name: "What usage statistics send" })
    )
    const usageDetails = (await screen.findByRole("tooltip")).textContent
    expect(usageDetails).toContain(
      "During the install’s first week it sends one more each time setup reaches a new step, at most four more."
    )
    expect(usageDetails).toContain("whether the model runtime can use the card")
    expect(usageDetails).toContain(
      "in the first week they go again only while part of them is unknown"
    )
    expect(usageDetails).toContain(
      "Never documents, prompts, file names, model names, hosts, your license key or an ID."
    )
  })

  it("holds Check now when a policy turned update checks off", async () => {
    stubPrivacyBridge({ updates: { locked: true, lockedReason: "policy" } })
    render(<UpdateSettings />)

    expect(
      await screen.findByText(
        "Your organization’s policy turned update checks off on this computer."
      )
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Check now" }).hasAttribute("disabled")
    ).toBe(true)
  })

  it.each([
    ["snap", "the Snap Store"],
    ["aur", "the AUR"],
    ["apt", "your apt repository"],
  ] as const)(
    "under %s, says only where updates come from",
    async (channel, name) => {
      stubPrivacyBridge({
        updates: { locked: true, lockedReason: "channel", channel },
      })
      render(<UpdateSettings />)

      expect(
        await screen.findByText(
          `Updates come from ${name}, so SurfSense doesn’t check for them itself.`
        )
      ).toBeTruthy()
      // SurfSense never asks its feed here, so nothing promises a daily check
      // or offers to show what one sends.
      expect(screen.queryByText(/once a day/)).toBeNull()
      expect(
        screen.queryByRole("button", { name: "Show exactly what’s sent" })
      ).toBeNull()
      expect(
        screen
          .getByRole("button", { name: "Check now" })
          .hasAttribute("disabled")
      ).toBe(true)
    }
  )
})
