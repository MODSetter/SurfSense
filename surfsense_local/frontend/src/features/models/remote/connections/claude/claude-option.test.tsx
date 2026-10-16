import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Connection } from "../api"
import { CLAUDE_INSTALL_URL, type ClaudeOption, type ClaudeStatus } from "./api"
import { ClaudeOption as ClaudeRow } from "./claude-option"

type Option = ClaudeOption & ClaudeStatus

const READY: Option = {
  state: "ready",
  version: "2.1.301",
  email: "ada@example.com",
  plan: "max",
  serves: ["text_gen"],
  hosts: [],
}

const CONNECTED: Connection = {
  id: 7,
  label: "Claude plan",
  provider: "openai_compatible",
  base_url: "https://api.anthropic.com",
  catalog_provider: "anthropic",
  has_api_key: false,
  auth_kind: "claude_plan",
  signed_in: false,
  account_email: null,
  serves: ["text_gen"],
  created_at: "2026-10-16T00:00:00",
  updated_at: "2026-10-16T00:00:00",
}

/** The API as the row and dialog see it: each status read takes the next of `states`. */
function serve(
  states: Partial<Option>[],
  { connected = false, checking = false } = {}
) {
  let made = connected
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/connections/claude" && init?.method === "POST") {
        made = true
        return Response.json(CONNECTED, { status: 201 })
      }
      if (path === "/llm/connections/claude") {
        const { serves, hosts } = { ...READY, ...states[0] }
        return Response.json({ serves, hosts })
      }
      if (path === "/llm/connections/claude/status") {
        // Claude Code is still being run: the answer never comes in this test.
        if (checking) return new Promise<Response>(() => {})
        const { state, version, email, plan } = {
          ...READY,
          ...(states.length > 1 ? states.shift() : states[0]),
        }
        return Response.json({ state, version, email, plan })
      }
      if (path === "/llm/connections")
        return Response.json(made ? [CONNECTED] : [])
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  window.surfsense = {
    openExternal: vi.fn(async () => {}),
  } as unknown as typeof window.surfsense
  return fetchMock
}

const setUp = () => screen.findByRole("button", { name: "Set up" })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete window.surfsense
})

describe("the Claude plan option beside the ChatGPT one", () => {
  it("is shown before Claude Code is checked, installed or not", async () => {
    serve([{}], { checking: true })
    render(<ClaudeRow modelType="text_gen" onConnected={vi.fn()} />)

    expect(await setUp()).toBeTruthy()
  })

  it("is offered only where a Claude plan can fill the slot", async () => {
    serve([{}])
    render(<ClaudeRow modelType="video_gen" onConnected={vi.fn()} />)

    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Use your Claude plan" })
      ).toBeNull()
    )
  })

  it("says to install Claude Code, and opens Anthropic’s guide", async () => {
    serve([{ state: "not_installed", version: null, email: null, plan: null }])
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await setUp())
    expect(
      await screen.findByText("Install Claude Code on this computer.")
    ).toBeTruthy()
    expect(
      screen.getByText("Then come back here and click Check again.")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Open install guide" }))

    expect(window.surfsense?.openExternal).toHaveBeenCalledWith(
      CLAUDE_INSTALL_URL
    )
  })

  it("checks again after the user signs in in a terminal", async () => {
    serve([{ state: "signed_out", email: null, plan: null }, {}])
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await setUp())
    expect(
      await screen.findByText(/not signed in to a Claude plan/)
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Check again" }))

    expect(
      await screen.findByText(/Connected as ada@example.com, Max plan/)
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Add Claude models" })
    ).toBeTruthy()
  })

  it("names the version when Claude Code is too old", async () => {
    serve([{ state: "too_old", version: "2.0.12", email: null, plan: null }])
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await setUp())

    expect(
      await screen.findByText(/Claude Code 2.0.12 is too old/)
    ).toBeTruthy()
  })

  it("adds the plan and hands over the new connection", async () => {
    const fetchMock = serve([{}])
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={onConnected} />)

    await user.click(await setUp())
    await user.click(
      await screen.findByRole("button", { name: "Add Claude models" })
    )

    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(CONNECTED))
    const made = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/connections/claude" && init?.method === "POST"
    )
    expect(JSON.parse(String(made?.[1]?.body))).toEqual({
      label: "Claude plan",
    })
  })

  it("makes nothing while a host it needs stays off", async () => {
    const fetchMock = serve([
      {
        hosts: [
          { destination: "host:api.anthropic.com", host: "api.anthropic.com" },
        ],
      },
    ])
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={vi.fn()} />)

    await user.click(await setUp())
    await user.click(
      await screen.findByRole("button", { name: "Add Claude models" })
    )

    expect(
      await screen.findByText(
        "Your Claude plan needs api.anthropic.com. Allow it to connect."
      )
    ).toBeTruthy()
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) =>
          path === "/llm/connections/claude" && init?.method === "POST"
      )
    ).toBe(false)
  })

  it("opens the models of a plan already connected", async () => {
    serve([{}], { connected: true })
    const onConnected = vi.fn()
    const user = userEvent.setup()
    render(<ClaudeRow modelType="text_gen" onConnected={onConnected} />)

    await user.click(await screen.findByRole("button", { name: "Show models" }))

    expect(onConnected).toHaveBeenCalledWith(CONNECTED)
  })
})
