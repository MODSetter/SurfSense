import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { DashboardPage } from "@/features/dashboard/dashboard-page"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

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

// What the backend answers a turn once the selected model cannot run the agent.
const REFUSAL =
  "The selected model cannot run the agent. Choose another model, or start a new chat to use this one."

function refusingBackend() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/documents")) return Response.json([])
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/chat/threads/10/messages" && init?.method === "POST") {
        return Response.json({ detail: REFUSAL }, { status: 409 })
      }
      if (path === "/chat/threads/10/messages") return Response.json([])
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
}

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

describe("an agent thread whose selected model cannot run the agent", () => {
  it("says the thread can't continue with it, and offers a new chat", async () => {
    refusingBackend()
    localStorage.setItem("surfsense:last-thread:1:v1", "10")
    render(
      <DashboardPage
        initialProviderAvailable={true}
        selection={selection}
        initialWorkspaces={[workspace]}
        onModelSelected={vi.fn()}
      />
    )
    const user = userEvent.setup()
    const composer = await screen.findByRole("textbox", { name: "Message" })
    await user.type(composer, "Summarise the contracts{Enter}")

    const conversation = screen.getByRole("region", { name: "Conversation" })
    expect(
      await within(conversation).findByText(
        /can’t continue with the selected model/
      )
    ).toBeTruthy()
    // The thread keeps its engine, so Retry would meet the same refusal.
    expect(
      within(conversation).queryByRole("button", { name: "Retry" })
    ).toBeNull()
    await user.click(
      within(conversation).getByRole("button", { name: "Start a new chat" })
    )

    await waitFor(() => {
      expect(
        screen
          .getByRole("textbox", { name: "Message" })
          .closest('[data-composer-placement="center"]')
      ).toBeTruthy()
    })
  })
})
