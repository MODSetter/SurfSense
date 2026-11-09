import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { AgentSteps } from "@/features/agent/agent-steps"
import type { AgentStep } from "@/features/agent/api"
import { render } from "@/test-utils"

import type { Plugin } from "../api"

const NOTES: Plugin = {
  id: "notes",
  name: "Notes",
  source: "custom",
  url: "https://notes.example/mcp",
  hosts: ["notes.example"],
  auth_type: "none",
  header_names: [],
  transport: "streamable_http",
  needs_scopes: [],
  own_app: false,
  needs_own_app: null,
  never_signed_in: false,
  enabled: true,
  disconnected: false,
  connected_at: "2026-10-01T00:00:00Z",
  checked_at: "2026-10-01T00:00:00Z",
  check_failure: null,
  removed_reason: null,
  tools: [
    {
      name: "search",
      title: "Search notes",
      description: "Search the notes.",
      annotations: { readOnlyHint: true },
      enabled: true,
      approval: "always",
      change: null,
    },
  ],
}

const STEP: AgentStep = {
  id: "prt_9",
  tool: "notes_search",
  status: "completed",
  input: { query: "ship" },
  output: "found ship, the start",
}

type Call = { method: string; path: string }

function api(): Call[] {
  const calls: Call[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://api.test").pathname
      const method = (init?.method ?? "GET").toUpperCase()
      calls.push({ method, path })
      if (path === "/plugins") return Response.json([NOTES])
      if (path.endsWith("/result")) {
        return Response.json({
          output: "found ship, the start and the rest",
          error: null,
        })
      }
      return Response.json({ document_id: 31 }, { status: 201 })
    })
  )
  return calls
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("a plugin's step", () => {
  it("names the plugin and the tool, not opencode's name for it", async () => {
    api()
    render(<AgentSteps steps={[STEP]} threadId={7} />)

    expect(await screen.findByText("Notes: Search notes")).toBeTruthy()
  })

  it("shows the whole result once opened, and saves it to Sources", async () => {
    const calls = api()
    const user = userEvent.setup()
    render(<AgentSteps steps={[STEP]} threadId={7} />)

    await user.click(await screen.findByText("Notes: Search notes"))
    expect(
      await screen.findByText("found ship, the start and the rest")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Save to Sources" }))

    expect(await screen.findByText("Saved to Sources")).toBeTruthy()
    expect(calls.filter((call) => call.method === "POST")).toEqual([
      { method: "POST", path: "/chat/threads/7/plugin-steps/prt_9/save" },
    ])
  })
})
