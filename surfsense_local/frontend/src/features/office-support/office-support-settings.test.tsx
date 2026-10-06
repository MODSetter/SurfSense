import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { OfficeStatus } from "./api"
import { OfficeSupportSettings } from "./office-support-settings"

const OFFER = {
  version: "26.8.0.3",
  size: 374_906_880,
  host: "downloadarchive.documentfoundation.org",
  destination: "host:downloadarchive.documentfoundation.org",
}

function status(extra: Partial<OfficeStatus> = {}): OfficeStatus {
  return {
    state: "not_installed",
    version: null,
    path: null,
    progress: null,
    error: null,
    offer: OFFER,
    detected: null,
    ...extra,
  }
}

type Call = { method: string; path: string; body: unknown }

/** The API as Settings reaches it: each call recorded, each answer the state given. */
function api(now: OfficeStatus, after: OfficeStatus = now): Call[] {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://api.test")
      const method = (init?.method ?? "GET").toUpperCase()
      calls.push({
        method,
        path: url.pathname,
        body: init?.body ? JSON.parse(String(init.body)) : null,
      })
      if (url.pathname.endsWith("/events")) {
        return new Response(JSON.stringify(now) + "\n", {
          headers: { "Content-Type": "application/x-ndjson" },
        })
      }
      if (url.pathname.startsWith("/egress/")) {
        return Response.json({
          destination: OFFER.destination,
          host: OFFER.host,
          enabled: true,
          last_call_at: null,
        })
      }
      return Response.json(method === "GET" ? now : after)
    })
  )
  return calls
}

const changes = (calls: Call[]) => calls.filter((call) => call.method !== "GET")

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("office support settings", () => {
  it("downloads only after a consent that names The Document Foundation, the host and the size", async () => {
    const calls = api(
      status(),
      status({ state: "downloading", progress: { completed: 0, total: 1 } })
    )
    const user = userEvent.setup()
    render(<OfficeSupportSettings />)

    await user.click(await screen.findByRole("button", { name: "Turn on" }))
    const consent = await screen.findByRole("alertdialog")
    expect(consent.textContent).toContain("The Document Foundation")
    expect(consent.textContent).toContain(OFFER.host)
    expect(consent.textContent).toContain("375")
    expect(changes(calls)).toEqual([])

    await user.click(within(consent).getByRole("button", { name: "Download" }))

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "PUT",
          path: `/egress/${OFFER.destination}`,
          body: { enabled: true },
        },
        { method: "POST", path: "/runtime-packs/office/install", body: null },
      ])
    )
    expect(await screen.findByText("Downloading LibreOffice…")).toBeTruthy()
  })

  it("leaves everything off when the consent is declined", async () => {
    const calls = api(status())
    const user = userEvent.setup()
    render(<OfficeSupportSettings />)

    await user.click(await screen.findByRole("button", { name: "Turn on" }))
    await user.click(await screen.findByRole("button", { name: "Not now" }))

    expect(changes(calls)).toEqual([])
  })

  it("offers the LibreOffice the user already has, once confirmed", async () => {
    const calls = api(
      status({
        detected: {
          path: "C:\\Program Files\\LibreOffice",
          branch: "26.8",
          usable: true,
          refusal: null,
        },
      }),
      status({
        state: "using_installed",
        version: "26.8",
        path: "C:\\Program Files\\LibreOffice",
      })
    )
    const user = userEvent.setup()
    render(<OfficeSupportSettings />)

    expect(
      await screen.findByText("LibreOffice 26.8 is installed")
    ).toBeTruthy()
    await user.click(
      screen.getByRole("button", { name: "Use the LibreOffice I have" })
    )

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        {
          method: "POST",
          path: "/runtime-packs/office/use-installed",
          body: null,
        },
      ])
    )
    expect(await screen.findByText("On: LibreOffice 26.8")).toBeTruthy()
  })

  it("says why an installed LibreOffice cannot be used, and offers nothing to click for it", async () => {
    api(
      status({
        detected: {
          path: "C:\\Program Files\\LibreOffice",
          branch: "25.2",
          usable: false,
          refusal: "branch_ended",
        },
      })
    )
    render(<OfficeSupportSettings />)

    expect(
      await screen.findByText(
        "This version no longer receives security fixes. Update LibreOffice to use it here."
      )
    ).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Use the LibreOffice I have" })
    ).toBeNull()
  })

  it("removes Office support once it is on", async () => {
    const calls = api(
      status({ state: "installed", version: "26.8.0.3" }),
      status()
    )
    const user = userEvent.setup()
    render(<OfficeSupportSettings />)

    expect(await screen.findByText("On: LibreOffice 26.8.0.3")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Remove" }))

    await waitFor(() =>
      expect(changes(calls)).toEqual([
        { method: "DELETE", path: "/runtime-packs/office", body: null },
      ])
    )
  })

  it("says why the LibreOffice the user has was refused when they try it", async () => {
    const found = status({
      detected: {
        path: "C:\\Program Files\\LibreOffice",
        branch: "26.8",
        usable: true,
        refusal: null,
      },
    })
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = new URL(String(input), "http://api.test").pathname
        if (path.endsWith("/events")) {
          return new Response(JSON.stringify(found) + "\n")
        }
        if (init?.method === "POST") {
          return Response.json(
            { detail: { code: "smoke_failed", message: "no PDF" } },
            { status: 409 }
          )
        }
        return Response.json(found)
      })
    )
    const user = userEvent.setup()
    render(<OfficeSupportSettings />)

    await user.click(
      await screen.findByRole("button", { name: "Use the LibreOffice I have" })
    )

    expect((await screen.findByRole("alert")).textContent).toBe(
      "It did not convert a test file."
    )
  })
})
