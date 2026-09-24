import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ChatModelsSettings } from "./chat-models-settings"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const budget = {
  device_total_bytes: 16_000_000_000,
  device_free_bytes: 14_000_000_000,
  usable_vram_bytes: 12_900_000_000,
  fit_reserve_bytes: 1_073_741_824,
  ram_available_bytes: 16_000_000_000,
  uma: true,
  has_gpu: true,
}

function build(overrides: Record<string, unknown> = {}) {
  return {
    catalog_id: "opaque-qwen",
    quantization: "Q4_K_M",
    footprint_bytes: 5_000_000_000,
    files: [],
    fit: {
      state: "fits",
      need_bytes: 0,
      budget_bytes: 0,
      offload_fraction: 0,
      approximate: false,
    },
    badge: { level: "none", verdict: "", reason: "" },
    can_install: true,
    installed_as: null,
    selected: false,
    recommended: false,
    reads_images: false,
    projector_checked: true,
    bundled: false,
    ...overrides,
  }
}

function row(overrides: Record<string, unknown> = {}, builds = [build()]) {
  return {
    id: "qwen3-8b",
    source: "local",
    origin: "curated",
    name: "Qwen3 8B",
    family: "Qwen3",
    types: ["text_gen"],
    known: true,
    approximate: false,
    selectable_for: ["text_gen"],
    support: {
      context: null,
      reads_images: false,
      tools: null,
      reasoning: null,
    },
    runnable: true,
    not_runnable_reason: null,
    builds,
    default_quantization: "Q4_K_M",
    recommended: false,
    engine: "llamacpp",
    lead: { quantization: "Q4_K_M", why: "recommended" },
    ...overrides,
  }
}

function serving({
  rows = [] as unknown[],
  selection = null as Record<string, unknown> | null,
  connections = [] as unknown[],
  extra = (() => null) as (path: string, init?: RequestInit) => Response | null,
} = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    const handled = extra(path, init)
    if (handled) return handled
    if (path === "/llm/catalog/local") {
      return Response.json({
        budget,
        gpu_status: "present",
        rows,
        recommended_id: null,
      })
    }
    if (path === "/llm/selection/text_gen" && init?.method === "PUT") {
      return Response.json({
        model_type: "text_gen",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-09-24T00:00:00Z",
      })
    }
    if (path === "/llm/selection/text_gen") {
      return selection
        ? Response.json(selection)
        : Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json(connections)
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

function renderSettings(
  props: Partial<Parameters<typeof ChatModelsSettings>[0]> = {}
) {
  return render(
    <ChatModelsSettings
      onSelected={() => undefined}
      onModelUnavailable={() => undefined}
      {...props}
    />
  )
}

describe("chat model settings", () => {
  it("offers both ways to add a model on one page", async () => {
    // The server option is short and sits first, closed; the catalog follows.
    vi.stubGlobal("fetch", serving({ rows: [row()] }))
    const user = userEvent.setup()
    renderSettings()

    expect(await screen.findByText("No chat model yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Add model" }))

    expect(
      screen.getByRole("heading", { name: "Add a chat model" })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Connect" })).toBeTruthy()
    expect(screen.queryByLabelText("Base URL")).toBeNull()
    expect(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    ).toBeTruthy()
  })

  it("opens a new server's models once it is saved", async () => {
    let saved = false
    const server = {
      id: 7,
      label: "My vLLM",
      provider: "openai_compatible",
      base_url: "http://10.0.0.4:8000/v1",
      catalog_provider: "custom",
      has_api_key: false,
      created_at: "2026-09-24T00:00:00Z",
      updated_at: "2026-09-24T00:00:00Z",
    }
    vi.stubGlobal(
      "fetch",
      serving({
        extra: (path, init) => {
          if (path === "/llm/catalog/remote") return Response.json([])
          if (path === "/llm/connections" && init?.method === "POST") {
            saved = true
            return Response.json(server)
          }
          if (path === "/llm/connections") {
            return Response.json(saved ? [server] : [])
          }
          if (path === "/llm/connections/7/models") return Response.json([])
          return null
        },
      })
    )
    const user = userEvent.setup()
    renderSettings()

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(screen.getByRole("button", { name: "Connect" }))
    const dialog = screen.getByRole("dialog", { name: "Connect a server" })
    await user.type(within(dialog).getByLabelText("Name"), "My vLLM")
    await user.type(
      within(dialog).getByLabelText("Base URL"),
      "http://10.0.0.4:8000/v1"
    )
    await user.click(
      within(dialog).getByRole("button", { name: "Save server" })
    )

    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Connect a server" })
      ).toBeNull()
    )
    // Back on the list with the new server open: its models are what the
    // user added it for.
    expect(
      await screen.findByRole("heading", { name: "Text generation models" })
    ).toBeTruthy()
    expect(
      await screen.findByLabelText("Search models from My vLLM")
    ).toBeTruthy()
  })

  it("can use a model on disk that no curated row covers", async () => {
    // A model installed from search is in the directory and not the manifest,
    // so this list is the only place it can be chosen from.
    const fetchMock = serving({
      rows: [
        row(
          {
            id: "some-searched-model",
            origin: "downloaded",
            name: "some-searched-model",
            family: "",
          },
          [build({ catalog_id: "", installed_as: "some-searched-model" })]
        ),
      ],
    })
    vi.stubGlobal("fetch", fetchMock)
    const onSelected = vi.fn()
    const user = userEvent.setup()

    renderSettings({ onSelected })
    await user.click(
      await screen.findByRole("button", { name: "Use some-searched-model" })
    )

    await waitFor(() => expect(onSelected).toHaveBeenCalledOnce())
    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/text_gen" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
      provider: "llamacpp",
      name: "some-searched-model",
    })
  })

  it("leaves an image model on disk to the image page", async () => {
    vi.stubGlobal(
      "fetch",
      serving({
        rows: [
          row({}, [build({ installed_as: "Qwen3-8B-Q4_K_M" })]),
          row(
            {
              id: "sdxl-turbo",
              name: "SDXL Turbo",
              family: "Stable Diffusion",
              types: ["image_gen"],
              selectable_for: ["image_gen"],
              engine: "sdcpp",
            },
            [build({ installed_as: "sdxl-turbo-q4_0", fit: null, badge: null })]
          ),
        ],
      })
    )

    renderSettings()

    expect(await screen.findByText("Qwen3 8B Q4_K_M")).toBeTruthy()
    expect(screen.queryByText(/SDXL Turbo/)).toBeNull()
  })

  it("reports the chat slot cleared when the model in use is deleted", async () => {
    vi.stubGlobal(
      "fetch",
      serving({
        rows: [
          row({}, [build({ installed_as: "Qwen3-8B-Q4_K_M", selected: true })]),
        ],
        extra: (path, init) =>
          path === "/llm/models/Qwen3-8B-Q4_K_M" && init?.method === "DELETE"
            ? Response.json({
                name: "Qwen3-8B-Q4_K_M",
                selection_cleared: true,
              })
            : null,
      })
    )
    const onModelUnavailable = vi.fn()
    const user = userEvent.setup()

    renderSettings({ onModelUnavailable })
    await user.click(
      await screen.findByRole("button", { name: "Delete Qwen3 8B Q4_K_M" })
    )
    expect(screen.getByText(/This is your current model/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete model" }))

    await waitFor(() => expect(onModelUnavailable).toHaveBeenCalledOnce())
  })

  it("names the server a model in use comes from", async () => {
    vi.stubGlobal(
      "fetch",
      serving({
        selection: {
          model_type: "text_gen",
          provider: "openai_compatible",
          connection_id: 9,
          name: "gpt-4o-mini",
          updated_at: "2026-09-24T00:00:00Z",
        },
        connections: [
          {
            id: 9,
            label: "OpenRouter",
            provider: "openai_compatible",
            base_url: "https://openrouter.ai/api/v1",
            catalog_provider: "openrouter",
            has_api_key: true,
            created_at: "2026-09-24T00:00:00Z",
            updated_at: "2026-09-24T00:00:00Z",
          },
        ],
      })
    )
    renderSettings()

    // Said above the groups, since the server's own list starts closed.
    const inUse = await screen.findByRole("region", {
      name: "chat model in use",
    })
    await waitFor(() => expect(inUse.textContent).toContain("gpt-4o-mini"))
    expect(inUse.textContent).toContain("OpenRouter")
    // And inside its server's group, which lists nothing else until opened.
    expect(
      screen.getByRole("button", { name: "Show chat models" })
    ).toBeTruthy()
  })

  it("keeps a download going after leaving the catalog", async () => {
    // The download belongs to the app, not the view: going back to the list
    // shows its progress there instead of cancelling it.
    let release = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const encoder = new TextEncoder()
    vi.stubGlobal(
      "fetch",
      serving({
        rows: [row()],
        extra: (path) =>
          path === "/llm/install"
            ? new Response(
                new ReadableStream<Uint8Array>({
                  async start(controller) {
                    controller.enqueue(
                      encoder.encode(
                        '{"type":"downloading","completed":5,"total":10}\n'
                      )
                    )
                    await held
                    controller.close()
                  },
                })
              )
            : null,
      })
    )
    const user = userEvent.setup()

    renderSettings()
    await user.click(await screen.findByRole("button", { name: "Add model" }))
    expect(
      screen.getByRole("heading", { name: "Add a chat model" })
    ).toBeTruthy()
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )
    expect(await screen.findByRole("progressbar")).toBeTruthy()

    await user.click(
      screen.getByRole("button", { name: "Text generation models" })
    )

    expect(
      screen.getByRole("heading", { name: "Text generation models" })
    ).toBeTruthy()
    expect(await screen.findByText("Qwen3 8B Q4_K_M")).toBeTruthy()
    expect(screen.getByRole("progressbar")).toBeTruthy()

    release()
    await waitFor(() => expect(screen.queryByRole("progressbar")).toBeNull())
  })
})
