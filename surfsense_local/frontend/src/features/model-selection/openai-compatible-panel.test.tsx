import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { OpenAICompatiblePanel } from "./openai-compatible-panel"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const connections = [
  {
    id: 1,
    label: "Chat gateway",
    provider: "openai_compatible",
    base_url: "https://chat.example/v1",
    has_api_key: true,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
  },
  {
    id: 2,
    label: "Image gateway",
    provider: "openai_compatible",
    base_url: "https://image.example/v1",
    has_api_key: false,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
  },
]

describe("OpenAI-compatible connections", () => {
  it("loads and searches models only after opening a connection", async () => {
    let resolveSlow!: (response: Response) => void
    const slow = new Promise<Response>((resolve) => {
      resolveSlow = resolve
    })
    const selections: Partial<
      Record<"generation" | "image_generation", Record<string, unknown>>
    > = {}
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/connections") return Response.json(connections)
        if (path.startsWith("/llm/selection/")) {
          const role = path.endsWith("image_generation")
            ? "image_generation"
            : "generation"
          if (init?.method === "PUT") {
            const body = JSON.parse(String(init.body))
            selections[role] = {
              role,
              ...body,
              updated_at: "2026-09-10T00:00:00Z",
            }
            return Response.json(selections[role])
          }
          if (!selections[role]) {
            return Response.json({ detail: "not selected" }, { status: 404 })
          }
          return Response.json(selections[role])
        }
        if (path === "/llm/connections/1/models") return slow
        if (path === "/llm/connections/2/models") {
          return Response.json([
            {
              connection_id: 2,
              connection_label: "Image gateway",
              name: "shared-model",
              capabilities: [],
              capability_known: false,
            },
          ])
        }
        if (
          path === "/llm/connections/2/image-test" &&
          init?.method === "POST"
        ) {
          return new Response(new Uint8Array([1, 2, 3]), {
            headers: { "Content-Type": "image/png" },
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:test-image"),
      revokeObjectURL: vi.fn(),
    })
    const onGenerationSelected = vi.fn()
    const user = userEvent.setup()

    render(
      <OpenAICompatiblePanel
        disabled={false}
        onGenerationSelected={onGenerationSelected}
        onChanged={() => undefined}
      />
    )

    expect(await screen.findByText("Chat gateway")).toBeTruthy()
    expect(screen.queryByText("shared-model")).toBeNull()
    expect(
      fetchMock.mock.calls.some(([path]) => String(path).endsWith("/models"))
    ).toBe(false)
    expect(
      screen.getByText("Chat gateway").closest('[data-slot="card"]')
        ?.parentElement?.className
    ).toContain("pl-px")

    const browseButtons = screen.getAllByRole("button", {
      name: "Browse models",
    })
    await user.click(browseButtons[1])
    expect(await screen.findByText("shared-model")).toBeTruthy()
    expect(
      fetchMock.mock.calls.some(
        ([path]) => path === "/llm/connections/1/models"
      )
    ).toBe(false)
    const exactModelInput = screen.getByLabelText("Exact model ID")
    const searchInput = screen.getByLabelText(
      "Search models from Image gateway"
    )
    expect(
      exactModelInput.compareDocumentPosition(searchInput) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
    expect(
      searchInput.closest('[data-slot="dialog-content"]')?.className
    ).toContain("select-none")
    expect(searchInput).toBe(document.activeElement)

    await user.type(searchInput, "missing")
    expect(await screen.findByText("No matching models")).toBeTruthy()
    await user.clear(searchInput)

    const fastModel = screen.getByText("shared-model").closest("li")
    const chatButton = fastModel?.querySelector("button")
    const imageButton = fastModel?.querySelectorAll("button")[1]
    if (!chatButton || !imageButton) throw new Error("model actions missing")
    await user.click(chatButton)
    await waitFor(() => expect(onGenerationSelected).toHaveBeenCalledOnce())
    const inUseChat = screen.getByRole("button", { name: "In use for chat" })
    expect(inUseChat.textContent).toBe("In use")
    expect(inUseChat.hasAttribute("disabled")).toBe(true)
    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/generation" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toEqual({
      provider: "openai_compatible",
      connection_id: 2,
      name: "shared-model",
      allow_unlisted: false,
    })

    await user.click(imageButton)
    expect(
      screen.getByText(/must implement.*images\/generations/s)
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Test image" }))
    expect(
      await screen.findByRole("img", { name: /Test generated by shared-model/ })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Use for image" }))
    const inUseImage = await screen.findByRole("button", {
      name: "In use for image",
    })
    expect(inUseImage.textContent).toBe("In use")
    expect(inUseImage.hasAttribute("disabled")).toBe(true)
    const imageWrite = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/image_generation" && init?.method === "PUT"
    )
    expect(JSON.parse(String(imageWrite?.[1]?.body)).allow_unlisted).toBe(true)

    const closeButtons = screen.getAllByRole("button", { name: "Close" })
    const closeButton = closeButtons.at(-1)
    if (!closeButton) throw new Error("model browser close button missing")
    await user.click(closeButton)
    await user.click(
      screen.getAllByRole("button", { name: "Browse models" })[0]
    )
    expect(screen.getByRole("status", { name: "Loading models" })).toBeTruthy()
    resolveSlow(
      Response.json([
        {
          connection_id: 1,
          connection_label: "Chat gateway",
          name: "shared-model",
          capabilities: ["completion"],
          capability_known: true,
        },
      ])
    )
    expect(await screen.findByText("shared-model")).toBeTruthy()
  })

  it("requires explicit Save anyway and names cleared roles", async () => {
    let list = connections.slice(0, 1)
    let createAttempts = 0
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/llm/connections" && init?.method === "POST") {
          createAttempts += 1
          const body = JSON.parse(String(init.body))
          if (!body.allow_unverified) {
            return Response.json(
              {
                detail: {
                  code: "unverified_connection",
                  message: "Model discovery is unavailable",
                },
              },
              { status: 422 }
            )
          }
          return Response.json({ ...connections[1], ...body })
        }
        if (path === "/llm/connections") return Response.json(list)
        if (path === "/llm/selection/generation") {
          return Response.json({
            role: "generation",
            provider: "openai_compatible",
            connection_id: 1,
            name: "chat",
            updated_at: "2026-09-10T00:00:00Z",
          })
        }
        if (path === "/llm/selection/image_generation") {
          return Response.json({
            role: "image_generation",
            provider: "openai_compatible",
            connection_id: 1,
            name: "image",
            updated_at: "2026-09-10T00:00:00Z",
          })
        }
        if (path === "/llm/connections/1/models") return Response.json([])
        if (path === "/llm/connections/1" && init?.method === "DELETE") {
          list = []
          return new Response(null, { status: 204 })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const onGenerationUnavailable = vi.fn()

    render(
      <OpenAICompatiblePanel
        disabled={false}
        onGenerationSelected={() => undefined}
        onGenerationUnavailable={onGenerationUnavailable}
        onChanged={() => undefined}
      />
    )

    await user.click(await screen.findByRole("button", { name: "Disconnect" }))
    expect(
      screen.getByText("Chat and Image roles will be cleared.")
    ).toBeTruthy()
    const confirm = screen.getAllByRole("button", { name: "Disconnect" }).at(-1)
    if (!confirm) throw new Error("disconnect confirmation missing")
    await user.click(confirm)
    await waitFor(() => expect(onGenerationUnavailable).toHaveBeenCalledOnce())

    await user.click(screen.getByRole("button", { name: "Add connection" }))
    expect(
      screen
        .getByLabelText("Connection label")
        .closest('[data-slot="dialog-content"]')?.className
    ).toContain("select-none")
    await user.type(screen.getByLabelText("Connection label"), "Images")
    await user.type(
      screen.getByLabelText("Base URL"),
      "https://images.example/v1"
    )
    await user.click(screen.getByRole("button", { name: "Save connection" }))
    expect(
      await screen.findByText("Model discovery is unavailable")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Save anyway" }))
    expect(createAttempts).toBe(2)
    const finalCreate = fetchMock.mock.calls.filter(
      ([path, init]) => path === "/llm/connections" && init?.method === "POST"
    )[1]
    expect(JSON.parse(String(finalCreate[1]?.body)).allow_unverified).toBe(true)
  })
})
