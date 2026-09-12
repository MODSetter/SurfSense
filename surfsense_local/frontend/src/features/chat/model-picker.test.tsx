import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ModelPicker } from "./model-picker"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("composer model picker", () => {
  it("searches installed models, selects one, and opens model management", async () => {
    const onModelSelected = vi.fn()
    const onManageModels = vi.fn()
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
          ])
        }
        if (path === "/llm/providers/ollama/models") {
          return Response.json([
            {
              name: "llama3.2:1b",
              installed: true,
              capabilities: ["completion"],
            },
            {
              name: "qwen3:1.7b",
              installed: true,
              capabilities: ["completion"],
            },
          ])
        }
        if (path === "/llm/selection/generation" && init?.method === "PUT") {
          return Response.json({
            role: "generation",
            provider: "ollama",
            connection_id: null,
            name: JSON.parse(String(init.body)).name,
            updated_at: "2026-09-09T00:00:00Z",
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <ModelPicker
        model={{
          role: "generation",
          provider: "ollama",
          connection_id: null,
          name: "llama3.2:1b",
          updated_at: "2026-09-09T00:00:00Z",
        }}
        onModelSelected={onModelSelected}
        onManageModels={onManageModels}
      />
    )

    await user.click(
      screen.getByRole("button", {
        name: "Model llama3.2:1b. Change model.",
      })
    )
    const search = await screen.findByRole("searchbox", {
      name: "Search models",
    })
    const currentItem = await screen.findByRole("menuitemradio", {
      name: "llama3.2:1b",
    })
    const availableItem = screen.getByRole("menuitemradio", {
      name: "qwen3:1.7b",
    })
    expect(currentItem.lastElementChild?.className).toContain(
      "sidebar-row-title-fade"
    )
    expect(availableItem.lastElementChild?.className).not.toContain("truncate")
    expect(availableItem.lastElementChild?.className).toContain(
      "sidebar-row-title-fade"
    )
    const results = document.querySelector(
      '[data-slot="scroll-shadow-viewport"]'
    ) as HTMLDivElement
    expect(results.parentElement?.className).toContain("h-60")
    const topShadow = document.querySelector('[data-slot="scroll-shadow-top"]')
    const bottomShadow = document.querySelector(
      '[data-slot="scroll-shadow-bottom"]'
    )
    expect(topShadow?.className).toContain("duration-100")
    expect(bottomShadow?.className).toContain("duration-100")
    Object.defineProperties(results, {
      clientHeight: { configurable: true, value: 256 },
      scrollHeight: { configurable: true, value: 512 },
      scrollTop: { configurable: true, value: 0, writable: true },
    })
    fireEvent.scroll(results)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-0")
      expect(bottomShadow?.className).toContain("opacity-100")
    })
    results.scrollTop = 256
    fireEvent.scroll(results)
    await waitFor(() => {
      expect(topShadow?.className).toContain("opacity-100")
      expect(bottomShadow?.className).toContain("opacity-0")
    })
    await user.type(search, "qwen")

    expect(
      screen.queryByRole("menuitemradio", { name: "llama3.2:1b" })
    ).toBeNull()
    await user.click(screen.getByRole("menuitemradio", { name: "qwen3:1.7b" }))

    await waitFor(() =>
      expect(onModelSelected).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "ollama", name: "qwen3:1.7b" })
      )
    )

    await user.click(
      screen.getByRole("button", {
        name: "Model llama3.2:1b. Change model.",
      })
    )
    await user.click(
      await screen.findByRole("menuitem", { name: "Manage models" })
    )
    expect(onManageModels).toHaveBeenCalledOnce()
  })

  it("scopes remote models to their connection and hides image-only entries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") return Response.json([])
        if (path === "/llm/connections") {
          return Response.json([
            {
              id: 7,
              label: "Internal gateway",
              provider: "openai_compatible",
              base_url: "http://models.internal/v1",
              has_api_key: false,
              created_at: "2026-09-10T00:00:00Z",
              updated_at: "2026-09-10T00:00:00Z",
            },
          ])
        }
        if (path === "/llm/connections/7/models") {
          return Response.json([
            {
              connection_id: 7,
              connection_label: "Internal gateway",
              name: "qwen-chat",
              capabilities: ["completion"],
              capability_known: true,
            },
            {
              connection_id: 7,
              connection_label: "Internal gateway",
              name: "flux-image",
              capabilities: ["image_generation"],
              capability_known: true,
            },
          ])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <ModelPicker
        model={{
          role: "generation",
          provider: "openai_compatible",
          connection_id: 7,
          name: "qwen-chat",
          updated_at: "2026-09-10T00:00:00Z",
        }}
        onModelSelected={() => undefined}
        onManageModels={() => undefined}
      />
    )
    await user.click(
      screen.getByRole("button", { name: "Model qwen-chat. Change model." })
    )

    const remote = await screen.findByRole("menuitemradio", {
      name: /qwen-chat/,
    })
    expect(remote.textContent).toContain("Internal gateway")
    expect(screen.queryByText("flux-image")).toBeNull()
  })
})
