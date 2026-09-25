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
  it("offers the remote models the backend says can fill the chat slot, unknown ones included", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/llm/providers") return Response.json([])
        if (path === "/llm/connections") {
          return Response.json([
            {
              id: 1,
              label: "Gateway",
              provider: "openai_compatible",
              base_url: "https://gw.example/v1",
              has_api_key: true,
              created_at: "2026-09-09T00:00:00Z",
              updated_at: "2026-09-09T00:00:00Z",
            },
          ])
        }
        if (path === "/llm/connections/1/models") {
          const listed = (
            name: string,
            types: string[],
            selectable_for: string[],
            capability_source: string
          ) => ({
            connection_id: 1,
            connection_label: "Gateway",
            name,
            types,
            capability_source,
            selectable_for,
          })
          return Response.json([
            listed("gpt-5", ["text_gen"], ["text_gen"], "catalog"),
            listed("gpt-image-2", ["image_gen"], ["image_gen"], "catalog"),
            listed(
              "acme/mystery-1",
              [],
              ["text_gen", "image_gen", "image_edit", "video_gen", "audio_gen"],
              "unknown"
            ),
          ])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <ModelPicker
        model={{
          model_type: "text_gen",
          provider: "openai_compatible",
          connection_id: 1,
          name: "gpt-5",
          updated_at: "2026-09-09T00:00:00Z",
        }}
        onModelSelected={vi.fn()}
        onManageModels={vi.fn()}
      />
    )

    await user.click(
      screen.getByRole("button", { name: "Model gpt-5. Change model." })
    )

    expect(
      await screen.findByRole("menuitemradio", { name: /gpt-5/ })
    ).toBeTruthy()
    expect(
      await screen.findByRole("menuitemradio", { name: /acme\/mystery-1/ })
    ).toBeTruthy()
    expect(
      screen.queryByRole("menuitemradio", { name: /gpt-image-2/ })
    ).toBeNull()
  })

  it("searches installed models, selects one, and opens model management", async () => {
    const onModelSelected = vi.fn()
    const onManageModels = vi.fn()
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/providers") {
          return Response.json([
            {
              name: "llamacpp",
              healthy: true,
              can_download: true,
              requires_key: false,
              configured: true,
            },
          ])
        }
        if (path === "/llm/providers/llamacpp/models") {
          return Response.json([
            {
              name: "llama3.2:1b",
              installed: true,
              capabilities: ["text_gen"],
              types: ["text_gen"],
              selectable_for: ["text_gen"],
            },
            {
              name: "qwen3:1.7b",
              installed: true,
              capabilities: ["text_gen"],
              types: ["text_gen"],
              selectable_for: ["text_gen"],
            },
          ])
        }
        if (path === "/llm/selection/text_gen" && init?.method === "PUT") {
          return Response.json({
            model_type: "text_gen",
            provider: "llamacpp",
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
          model_type: "text_gen",
          provider: "llamacpp",
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
    const availableItem = await screen.findByRole("menuitemradio", {
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
    await user.click(
      await screen.findByRole("menuitemradio", { name: "qwen3:1.7b" })
    )

    await waitFor(() =>
      expect(onModelSelected).toHaveBeenCalledWith(
        expect.objectContaining({ provider: "llamacpp", name: "qwen3:1.7b" })
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

  it("scopes remote models to their connection and hides known image models", async () => {
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
              types: ["text_gen"],
              capability_source: "declared",
              selectable_for: ["text_gen"],
            },
            {
              connection_id: 7,
              connection_label: "Internal gateway",
              name: "flux-image",
              types: ["image_gen"],
              capability_source: "declared",
              selectable_for: ["image_gen"],
            },
            // OpenAI and Gemini declare nothing, so their rows are answered
            // by the reviewed catalogue. A chat picker owes those the same
            // exclusions it owes a declaration.
            {
              connection_id: 7,
              connection_label: "Internal gateway",
              name: "gpt-image-1",
              types: ["image_gen"],
              capability_source: "catalog",
              selectable_for: ["image_gen"],
            },
            {
              connection_id: 7,
              connection_label: "Internal gateway",
              name: "whisper-1",
              types: [],
              capability_source: "unknown",
              selectable_for: [
                "text_gen",
                "image_gen",
                "image_edit",
                "video_gen",
                "audio_gen",
              ],
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
          model_type: "text_gen",
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
    expect(screen.queryByText("gpt-image-1")).toBeNull()
    // Unknown is not no: the backend offers it for every slot, so it is here.
    expect(
      await screen.findByRole("menuitemradio", { name: /whisper-1/ })
    ).toBeTruthy()
  })

  it("clears the search from its own button and keeps focus in the box", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(
      <ModelPicker
        model={{
          model_type: "text_gen",
          provider: "openai_compatible",
          connection_id: 1,
          name: "gpt-5",
          updated_at: "2026-09-09T00:00:00Z",
        }}
        onModelSelected={vi.fn()}
        onManageModels={vi.fn()}
      />
    )

    await user.click(
      screen.getByRole("button", { name: "Model gpt-5. Change model." })
    )
    const search = await screen.findByRole<HTMLInputElement>("searchbox", {
      name: "Search models",
    })
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()

    await user.type(search, "qwen")
    await user.click(screen.getByRole("button", { name: "Clear search" }))

    expect(search.value).toBe("")
    expect(document.activeElement).toBe(search)
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()
  })
})
