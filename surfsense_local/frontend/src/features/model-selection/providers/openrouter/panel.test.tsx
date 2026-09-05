import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ModelSelectionPage } from "../../model-selection-page"

function installApi() {
  const state = { configured: false }

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)

      if (path === "/llm/providers") {
        return Response.json([
          {
            name: "ollama",
            healthy: true,
            can_download: true,
            requires_key: false,
            configured: true,
          },
          {
            name: "openrouter",
            healthy: state.configured,
            can_download: false,
            requires_key: true,
            configured: state.configured,
          },
        ])
      }
      if (path === "/llm/providers/ollama/models") {
        return Response.json([])
      }
      if (path === "/llm/providers/ollama/catalog") {
        return Response.json([])
      }
      if (path === "/llm/providers/openrouter/models") {
        return Response.json(
          state.configured
            ? [
                {
                  name: "openai/gpt-4o",
                  installed: true,
                  capabilities: ["completion"],
                },
              ]
            : []
        )
      }
      if (
        path === "/llm/providers/openrouter/credentials" &&
        init?.method === "PUT"
      ) {
        state.configured = true
        return new Response(null, { status: 204 })
      }
      if (path === "/llm/selection/generation" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body)) as {
          provider: string
          name: string
        }
        return Response.json({
          role: "generation",
          ...payload,
          updated_at: "2026-09-05T00:00:00Z",
        })
      }
      if (path === "/llm/selection/generation") {
        return Response.json({ detail: "no model chosen" }, { status: 404 })
      }

      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )

  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
})

describe("openrouter provider", () => {
  it("connects a key, then selects and saves a remote model", async () => {
    const fetchMock = installApi()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelSelectionPage />)

    await user.click(await screen.findByRole("tab", { name: /openrouter/i }))

    await user.type(
      screen.getByLabelText("OpenRouter API key"),
      "sk-or-test-key"
    )
    await user.click(screen.getByRole("button", { name: "Connect" }))

    const model = await screen.findByRole("radio", { name: /gpt-4o/i })
    await user.click(model)
    await user.click(screen.getByRole("button", { name: "Use this model" }))

    await screen.findByText("Model selection saved.")

    const credential = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/providers/openrouter/credentials" &&
        init?.method === "PUT"
    )
    expect(JSON.parse(String(credential?.[1]?.body))).toEqual({
      api_key: "sk-or-test-key",
    })

    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/generation" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toEqual({
      provider: "openrouter",
      name: "openai/gpt-4o",
    })
  })
})
