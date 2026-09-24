import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ConnectionForm } from "../connections/connection-form"
import { ServerModelPicker } from "./server-model-picker"

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
    catalog_provider: "custom",
    has_api_key: true,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
  },
  {
    id: 2,
    label: "Image gateway",
    provider: "openai_compatible",
    base_url: "https://image.example/v1",
    catalog_provider: "custom",
    has_api_key: false,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
  },
]

const ALL_SLOTS = [
  "text_gen",
  "image_gen",
  "image_edit",
  "video_gen",
  "audio_gen",
]

const gatewayModels = [
  {
    connection_id: 1,
    connection_label: "Chat gateway",
    name: "gpt-image-1",
    types: ["image_gen"],
    capability_source: "catalog",
    selectable_for: ["image_gen"],
  },
  {
    connection_id: 1,
    connection_label: "Chat gateway",
    name: "gpt-4o-mini",
    types: ["text_gen"],
    capability_source: "catalog",
    selectable_for: ["text_gen"],
  },
  {
    connection_id: 1,
    connection_label: "Chat gateway",
    name: "whisper-1",
    types: [],
    capability_source: "unknown",
    selectable_for: ALL_SLOTS,
  },
]

/** A small in-memory backend: connections, their models, and the two slots. */
function serving(
  extra: (
    path: string,
    init?: RequestInit
  ) => Response | Promise<Response> | null = () => null
) {
  const selections: Record<string, unknown> = {}
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const handled = await extra(path, init)
    if (handled) return handled
    if (path === "/llm/connections") return Response.json([connections[0]])
    if (path === "/llm/connections/1/models")
      return Response.json(gatewayModels)
    if (path.startsWith("/llm/selection/")) {
      const slot = path.split("/").at(-1) ?? ""
      if (init?.method === "PUT") {
        selections[slot] = {
          model_type: slot,
          ...JSON.parse(String(init.body)),
          updated_at: "2026-09-10T00:00:00Z",
        }
      }
      return selections[slot]
        ? Response.json(selections[slot])
        : Response.json({ detail: "not selected" }, { status: 404 })
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("choosing a model from a server", () => {
  it("lists only the models that can fill this slot", async () => {
    // A guess from the model name is worth acting on: it hides a model from the
    // wrong slot, while one it cannot place at all is offered to every slot.
    vi.stubGlobal("fetch", serving())
    const user = userEvent.setup()

    render(<ServerModelPicker onEdit={() => undefined} modelType="text_gen" />)
    await user.click(
      await screen.findByRole("button", { name: "Show chat models" })
    )

    const list = await screen.findByRole("list", {
      name: "chat models on Chat gateway",
    })
    expect(within(list).getByText("gpt-4o-mini")).toBeTruthy()
    expect(within(list).getByText("whisper-1")).toBeTruthy()
    expect(within(list).queryByText("gpt-image-1")).toBeNull()
    expect(within(list).getByText("Capability unknown")).toBeTruthy()
  })

  it("offers image models in the image slot", async () => {
    vi.stubGlobal("fetch", serving())
    const user = userEvent.setup()

    render(<ServerModelPicker onEdit={() => undefined} modelType="image_gen" />)
    await user.click(
      await screen.findByRole("button", { name: "Show image models" })
    )

    const list = await screen.findByRole("list", {
      name: "image models on Chat gateway",
    })
    expect(within(list).getByText("gpt-image-1")).toBeTruthy()
    expect(within(list).queryByText("gpt-4o-mini")).toBeNull()
  })

  it("lists a server's models only once it is opened", async () => {
    const fetchMock = serving()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ServerModelPicker onEdit={() => undefined} modelType="text_gen" />)
    expect(await screen.findByText("Chat gateway")).toBeTruthy()
    expect(
      fetchMock.mock.calls.some(([path]) => String(path).endsWith("/models"))
    ).toBe(false)

    await user.click(screen.getByRole("button", { name: "Show chat models" }))
    expect(await screen.findByText("gpt-4o-mini")).toBeTruthy()

    await user.type(
      screen.getByLabelText("Search models from Chat gateway"),
      "missing"
    )
    expect(await screen.findByText(/No chat models match/)).toBeTruthy()
  })

  it("tests an unconfirmed model before it takes the chat slot", async () => {
    const fetchMock = serving((path, init) =>
      path === "/llm/connections/1/chat-test" && init?.method === "POST"
        ? Response.json({ reply: "Yes, I can answer." })
        : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const onSelected = vi.fn()
    const user = userEvent.setup()

    render(
      <ServerModelPicker
        onEdit={() => undefined}
        modelType="text_gen"
        onSelected={onSelected}
      />
    )
    await user.click(
      await screen.findByRole("button", { name: "Show chat models" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Use whisper-1" })
    )

    expect(screen.getByText(/chat support is unconfirmed/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Test chat" }))
    expect(await screen.findByText("Yes, I can answer.")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Use this model" }))

    await waitFor(() => expect(onSelected).toHaveBeenCalledOnce())
    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/text_gen" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toEqual({
      provider: "openai_compatible",
      connection_id: 1,
      name: "whisper-1",
      // Listed by the server, so the server's own check still applies.
      allow_unlisted: false,
    })
    const row = (await screen.findByText("whisper-1")).closest("li")
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("In use")).toBeTruthy()
    )
  })

  it("previews a test image before the model takes the image slot", async () => {
    vi.stubGlobal(
      "fetch",
      serving((path, init) =>
        path === "/llm/connections/1/image-test" && init?.method === "POST"
          ? new Response(new Uint8Array([1, 2, 3]), {
              headers: { "Content-Type": "image/png" },
            })
          : null
      )
    )
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:test-image"),
      revokeObjectURL: vi.fn(),
    })
    const user = userEvent.setup()

    render(<ServerModelPicker onEdit={() => undefined} modelType="image_gen" />)
    await user.click(
      await screen.findByRole("button", { name: "Show image models" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Use gpt-image-1" })
    )

    expect(screen.getByText(/Image support is confirmed/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Test image" }))
    expect(
      await screen.findByRole("img", { name: "Test generated by gpt-image-1" })
    ).toBeTruthy()
  })

  it("assigns a typed model id without the listing's check", async () => {
    const fetchMock = serving()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ServerModelPicker onEdit={() => undefined} modelType="text_gen" />)
    await user.click(
      await screen.findByRole("button", { name: "Show chat models" })
    )
    await user.type(
      await screen.findByLabelText("Exact model ID"),
      "org/new-model"
    )
    await user.click(screen.getByRole("button", { name: "Use for chat" }))
    await user.click(
      screen.getByRole("button", { name: "Use without testing" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/text_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        name: "org/new-model",
        allow_unlisted: true,
      })
    })
  })

  it("shows the model in use while its server's list is closed", async () => {
    const fetchMock = serving((path, init) =>
      path === "/llm/selection/text_gen" && !init?.method
        ? Response.json({
            model_type: "text_gen",
            provider: "openai_compatible",
            connection_id: 1,
            name: "gpt-4o-mini",
            updated_at: "2026-09-10T00:00:00Z",
          })
        : null
    )
    vi.stubGlobal("fetch", fetchMock)

    render(<ServerModelPicker onEdit={() => undefined} modelType="text_gen" />)

    expect(await screen.findByText("gpt-4o-mini")).toBeTruthy()
    expect(screen.getByRole("button", { name: "In use" })).toBeTruthy()
    // Named from the selection, so the server's list was never fetched.
    expect(
      fetchMock.mock.calls.some(([path]) => String(path).endsWith("/models"))
    ).toBe(false)
  })

  it("names every slot a server fills before removing it", async () => {
    // Servers are shared, so removing one from the chat page can clear the
    // image model too, and the confirmation has to say so.
    let list = connections.slice(0, 1)
    vi.stubGlobal(
      "fetch",
      serving((path, init) => {
        if (path === "/llm/connections" && !init?.method) {
          return Response.json(list)
        }
        if (path.startsWith("/llm/selection/")) {
          const slot = path.split("/").at(-1)
          return Response.json({
            model_type: slot,
            provider: "openai_compatible",
            connection_id: 1,
            name: slot === "text_gen" ? "chat" : "image",
            updated_at: "2026-09-10T00:00:00Z",
          })
        }
        if (path === "/llm/connections/1" && init?.method === "DELETE") {
          list = []
          return new Response(null, { status: 204 })
        }
        return null
      })
    )
    const onChatCleared = vi.fn()
    const user = userEvent.setup()

    render(
      <ServerModelPicker
        onEdit={() => undefined}
        modelType="image_gen"
        onChatCleared={onChatCleared}
      />
    )
    await user.click(
      await screen.findByRole("button", { name: "Disconnect Chat gateway" })
    )
    expect(
      await screen.findByText("Your Chat and Image models will be cleared.")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Disconnect" }))

    await waitFor(() => expect(onChatCleared).toHaveBeenCalledOnce())
    await waitFor(() => expect(screen.queryByText("Chat gateway")).toBeNull())
  })

  it("saves an unverifiable server only after Save anyway", async () => {
    let createAttempts = 0
    const fetchMock = serving((path, init) => {
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
      if (path === "/llm/catalog/remote") return Response.json([])
      return null
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <ConnectionForm onCancel={() => undefined} onSaved={() => undefined} />
    )
    await user.type(screen.getByLabelText("Connection label"), "Images")
    await user.type(
      screen.getByLabelText("Base URL"),
      "https://images.example/v1"
    )
    await user.click(screen.getByRole("button", { name: "Save server" }))
    expect(
      await screen.findByText("Model discovery is unavailable")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Save anyway" }))

    await waitFor(() => expect(createAttempts).toBe(2))
    const finalCreate = fetchMock.mock.calls.filter(
      ([path, init]) => path === "/llm/connections" && init?.method === "POST"
    )[1]
    expect(JSON.parse(String(finalCreate[1]?.body)).allow_unverified).toBe(true)
  })
})
