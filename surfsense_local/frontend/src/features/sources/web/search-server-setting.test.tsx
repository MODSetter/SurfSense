import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { SearchServerSetting } from "./search-server-setting"

const DEFAULT = "https://searxng.surfsense.com"

/** The API's search server route, keeping what it was sent. */
function serving(answer?: (url: string | null) => Response) {
  let url: string | null = null
  const sent: unknown[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/web-search/server")
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as { url: string | null }
        sent.push(body)
        const refused = answer?.(body.url)
        if (refused) return refused
        url = body.url
      }
      return Response.json({ url, default_url: DEFAULT })
    })
  )
  return sent
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the search server setting", () => {
  it("shows SurfSense's server until another is named", async () => {
    serving()
    render(<SearchServerSetting />)

    const field = await screen.findByRole("textbox", { name: "Web search" })

    await waitFor(() => expect(field.getAttribute("placeholder")).toBe(DEFAULT))
    expect((field as HTMLInputElement).value).toBe("")
    expect(screen.queryByRole("button", { name: "Use SurfSense’s" })).toBeNull()
  })

  it("saves a firm's own server, and goes back to SurfSense's on request", async () => {
    const sent = serving()
    const user = userEvent.setup()
    render(<SearchServerSetting />)

    await user.type(
      await screen.findByRole("textbox", { name: "Web search" }),
      "https://search.firm.example"
    )
    await user.click(screen.getByRole("button", { name: "Save" }))
    await user.click(
      await screen.findByRole("button", { name: "Use SurfSense’s" })
    )

    await waitFor(() =>
      expect(sent).toEqual([
        { url: "https://search.firm.example" },
        { url: null },
      ])
    )
    expect(
      (screen.getByRole("textbox", { name: "Web search" }) as HTMLInputElement)
        .value
    ).toBe("")
  })

  it("says what an address the server refused must look like", async () => {
    serving(() =>
      Response.json(
        { detail: [{ msg: "must be an http or https address" }] },
        { status: 422 }
      )
    )
    const user = userEvent.setup()
    render(<SearchServerSetting />)

    await user.type(
      await screen.findByRole("textbox", { name: "Web search" }),
      "search.firm.example"
    )
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(
      await screen.findByText(
        "Enter the server’s address, starting with https:// or http://."
      )
    ).toBeTruthy()
  })

  it("says the save failed, not what an address must look like, when the app errs", async () => {
    serving(() => new Response("Internal Server Error", { status: 500 }))
    const user = userEvent.setup()
    render(<SearchServerSetting />)

    await user.type(
      await screen.findByRole("textbox", { name: "Web search" }),
      "https://search.firm.example"
    )
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(
      await screen.findByText("Couldn’t save the search server. Try again.")
    ).toBeTruthy()
    expect(
      screen.queryByText(
        "Enter the server’s address, starting with https:// or http://."
      )
    ).toBeNull()
  })
})
