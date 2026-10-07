import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { DashboardPage } from "@/features/dashboard/dashboard-page"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import type { OfficeStatus } from "./api"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
}
const thread = {
  ...workspace,
  id: 10,
  workspace_id: 1,
  title: "Contracts",
  uses_agent: true,
}
const selection: ModelSelection = {
  model_type: "text_gen",
  provider: "openai_compatible",
  connection_id: 1,
  name: "remote-model",
  updated_at: "2026-10-01T00:00:00Z",
  reads_images: false,
}
const OFFER = {
  version: "26.8.0.3",
  size: 374_906_880,
  host: "downloadarchive.documentfoundation.org",
  destination: "host:downloadarchive.documentfoundation.org",
}

function office(extra: Partial<OfficeStatus> = {}): OfficeStatus {
  return {
    state: "not_installed",
    version: null,
    path: null,
    progress: null,
    error: null,
    offer: OFFER,
    detected: null,
    offer_dismissed: false,
    ...extra,
  }
}

function artifact(id: number, format: string) {
  return {
    id,
    document_id: 100 + id,
    format,
    generation: 1,
    title: "Client proposal",
    status: "ready",
    error_message: null,
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
    version: { root_id: id, number: 1, parent_id: null },
    spec_kind: "python",
    refinable: false,
  }
}

function reply(artifactId: number, tool = "surfsense_render_document") {
  return [
    {
      id: "msg_u1",
      role: "user",
      content: { text: "Draft the proposal" },
      created_at: "2026-10-01T00:00:00Z",
      completed_at: "2026-10-01T00:00:00Z",
    },
    {
      id: "msg_u1:reply",
      role: "assistant",
      content: {
        text: "Here it is.",
        steps: [
          {
            id: "prt_6",
            tool,
            status: "completed",
            title: "",
            input: { title: "Client proposal", format: "docx" },
            output: `Rendered artifact ${artifactId}, version 1.`,
            artifact: { id: artifactId, title: "Client proposal", version: 1 },
          },
        ],
      },
      created_at: "2026-10-01T00:00:01Z",
      completed_at: "2026-10-01T00:00:02Z",
    },
  ]
}

type Call = { method: string; path: string }

/** The API with one stored reply that made `made`, and Office support as `now`. */
function backend({
  made = artifact(41, "docx"),
  now = office(),
  stored = reply(41),
}: {
  made?: ReturnType<typeof artifact>
  now?: OfficeStatus
  stored?: unknown[]
} = {}): Call[] {
  const calls: Call[] = []
  let status = now
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      calls.push({ method, path })
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/documents")) return Response.json([])
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/chat/threads/10/messages") return Response.json(stored)
      if (path === "/workspaces/1/artifacts") return Response.json([made])
      if (path === "/runtime-packs/office/offer/dismiss") {
        status = { ...status, offer_dismissed: true }
        return Response.json(status)
      }
      if (path === "/runtime-packs/office/events") {
        return new Response(JSON.stringify(status) + "\n", {
          headers: { "Content-Type": "application/x-ndjson" },
        })
      }
      if (path === "/runtime-packs/office") return Response.json(status)
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return calls
}

function renderThread() {
  localStorage.setItem("surfsense:last-thread:1:v1", "10")
  render(
    <DashboardPage
      initialProviderAvailable={true}
      selection={selection}
      initialWorkspaces={[workspace]}
      onModelSelected={vi.fn()}
    />
  )
}

const OFFERED =
  /Get exact Office pages, real spreadsheet totals and conversion to PDF/

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  for (const method of ["scrollTo", "scrollIntoView"]) {
    Object.defineProperty(HTMLElement.prototype, method, {
      configurable: true,
      value: vi.fn(),
    })
  }
  vi.stubGlobal("surfsense", { apiUrl: "", platform: "darwin" })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("the Office support offer in an agent thread", () => {
  it("offers it under a reply that made a Word file, with this computer's download size", async () => {
    backend()
    renderThread()

    const offer = await screen.findByRole("region", {
      name: "Office support",
    })
    expect(offer.textContent).toMatch(OFFERED)
    expect(offer.textContent).toContain("375")
  })

  it("opens Settings at the download's consent and downloads nothing itself", async () => {
    const calls = backend()
    const user = userEvent.setup()
    renderThread()

    const offer = await screen.findByRole("region", {
      name: "Office support",
    })
    await user.click(
      within(offer).getByRole("button", { name: "Turn on Office support" })
    )

    const consent = await screen.findByRole("alertdialog")
    expect(consent.textContent).toContain("The Document Foundation")
    expect(
      calls.filter(
        (call) =>
          call.method !== "GET" &&
          (call.path.startsWith("/egress") || call.path.endsWith("/install"))
      )
    ).toEqual([])
  })

  it("never offers it again once dismissed", async () => {
    const calls = backend()
    const user = userEvent.setup()
    renderThread()

    const offer = await screen.findByRole("region", {
      name: "Office support",
    })
    await user.click(
      within(offer).getByRole("button", {
        name: "Dismiss the Office support offer",
      })
    )

    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Office support" })
      ).toBeNull()
    )
    expect(calls).toContainEqual({
      method: "POST",
      path: "/runtime-packs/office/offer/dismiss",
    })
  })

  it.each([
    ["dismissed before", office({ offer_dismissed: true })],
    ["already on", office({ state: "installed", version: "26.8.0.3" })],
    ["not offered for this computer", office({ offer: null })],
  ])("stays hidden when the offer was %s", async (_why, now) => {
    backend({ now })
    renderThread()

    await screen.findByText("Here it is.")
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole("region", { name: "Office support" })).toBeNull()
  })

  it("stays hidden under a reply that made no Office file", async () => {
    backend({ made: artifact(41, "pdf") })
    renderThread()

    await screen.findByText("Here it is.")
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole("region", { name: "Office support" })).toBeNull()
  })

  it("offers it for a revised copy too", async () => {
    backend({
      made: artifact(42, "xlsx"),
      stored: reply(42, "surfsense_revise_document"),
    })
    renderThread()

    expect(
      await screen.findByRole("region", { name: "Office support" })
    ).toBeTruthy()
  })
})
