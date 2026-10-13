import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Streamdown } from "streamdown"

import { STREAMDOWN_LINK_SAFETY } from "@/features/studio/viewers/streamdown-config"
import { render } from "@/test-utils"

/** A rendered reply holding one Markdown link, as chat and Studio render them. */
function reply(markdown: string) {
  render(
    <Streamdown linkSafety={STREAMDOWN_LINK_SAFETY}>{markdown}</Streamdown>
  )
}

function desktop() {
  const openConfirmedLink = vi.fn(async () => {})
  window.surfsense = { openConfirmedLink } as unknown as typeof window.surfsense
  return openConfirmedLink
}

afterEach(() => {
  cleanup()
  delete window.surfsense
})

describe("the link popup", () => {
  it("names a reply link's host and opens it only once confirmed", async () => {
    const opened = desktop()
    const user = userEvent.setup()
    reply("See [the page](https://app.notion.com/p/329aedcce14281f6).")

    await user.click(screen.getByText("the page"))

    const dialog = await screen.findByRole("dialog", {
      name: "Open app.notion.com?",
    })
    expect(dialog.textContent).toContain(
      "https://app.notion.com/p/329aedcce14281f6"
    )
    expect(opened).not.toHaveBeenCalled()
    expect(dialog.textContent).not.toContain("carries information")
    await user.click(screen.getByRole("button", { name: "Open link" }))

    expect(opened).toHaveBeenCalledWith(
      "https://app.notion.com/p/329aedcce14281f6"
    )
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })

  it("warns when a link's address carries information", async () => {
    desktop()
    const user = userEvent.setup()
    reply(`[a source](https://collect.example/?d=${"note-".repeat(30)})`)

    await user.click(screen.getByText("a source"))

    const dialog = await screen.findByRole("dialog")
    expect(dialog.textContent).toContain(
      "This address carries information. Only open it if you trust collect.example."
    )
  })

  it("copies a link instead of opening it", async () => {
    const opened = desktop()
    const user = userEvent.setup()
    reply("[docs](https://docs.example/start)")

    await user.click(screen.getByText("docs"))
    await user.click(await screen.findByRole("button", { name: "Copy link" }))

    expect(await navigator.clipboard.readText()).toBe(
      "https://docs.example/start"
    )
    expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy()
    expect(opened).not.toHaveBeenCalled()
  })
})
