import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { render } from "@/test-utils"
import { ModelCatalogPage } from "./model-catalog-page"
import { parseNdjson, type CatalogRow, type ModelCatalog } from "./api"

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
  },
}))

const row = (overrides: Partial<CatalogRow> = {}): CatalogRow => ({
  catalog_id: "opaque-qwen",
  canonical_id: "Qwen/Qwen3-8B",
  family: "Qwen",
  label: "Qwen 3 8B",
  publisher: "Qwen",
  parameter_count: 8_000_000_000,
  fit: "good",
  score: 92,
  memory_required_gb: 6.2,
  disk_size_gb: 5.1,
  estimated_tps: 24,
  prefill_tps: 100,
  ttft_ms: 240,
  effective_context_length: 8192,
  estimate_confidence: "high",
  license: "Apache-2.0",
  runtime: "ollama",
  runtime_model: "qwen3:8b",
  quantization: "Q4_K_M",
  installed: false,
  selected: false,
  can_install: true,
  can_delete: false,
  warnings: [],
  ...overrides,
})

const catalog = (overrides: Partial<ModelCatalog> = {}): ModelCatalog => ({
  hardware: {
    cpu_name: "Apple M3",
    cpu_cores: 8,
    total_ram_gb: 16,
    available_ram_gb: 12,
    has_gpu: true,
    gpu_name: "Apple M3",
    gpu_vram_gb: 16,
    gpu_count: 1,
    backend: "Metal",
    unified_memory: true,
  },
  llmfit_version: "1.1.11",
  recommended: [row()],
  explore: [],
  installed: [],
  warnings: [],
  runtime_status: { ollama: { available: true } },
  ...overrides,
})

function stream(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe("normalized model catalog", () => {
  it("parses NDJSON split across arbitrary chunks", async () => {
    const values = []
    for await (const value of parseNdjson<{ type: string }>(
      stream(['{"type":"start', 'ing"}\n{"type":"complete"}'])
    )) {
      values.push(value)
    }
    expect(values).toEqual([{ type: "starting" }, { type: "complete" }])
  })

  it("installs with only the opaque id and advances on complete", async () => {
    const onSelected = vi.fn()
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        void init
        const path = String(input)
        if (path === "/llm/catalog") {
          return Response.json(catalog())
        }
        if (path === "/llm/install") {
          return new Response(
            stream([
              '{"type":"downloading","message":"Downloading","completed":5,',
              '"total":10}\n',
              '{"type":"complete","selection":{"role":"generation","provider":"ollama","name":"qwen3:8b","updated_at":"2026-09-07T00:00:00Z"}}\n',
            ])
          )
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelCatalogPage onSelected={onSelected} />)
    const action = await screen.findByRole("button", {
      name: "Download",
    })
    expect(screen.getByText("Best for this computer")).toBeTruthy()
    expect(
      screen.getByText("Only models compatible with this computer are shown.")
    ).toBeTruthy()
    expect(screen.getByText("Good fit")).toBeTruthy()
    expect(screen.getByRole("list", { name: "Qwen models" })).toBeTruthy()
    expect(screen.getByRole("listitem")).toBeTruthy()
    expect(screen.getByText("5.1 GB")).toBeTruthy()
    await user.click(action)

    await waitFor(() => expect(onSelected).toHaveBeenCalledOnce())
    const installCall = fetchMock.mock.calls.find(
      ([path]) => path === "/llm/install"
    )
    expect(JSON.parse(String(installCall?.[1]?.body))).toEqual({
      catalog_id: "opaque-qwen",
      select: true,
    })
  })

  it("confirms marginal models and disables too-tight installs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          catalog({
            recommended: [],
            explore: [
              row({
                catalog_id: "marginal",
                label: "Marginal model",
                fit: "marginal",
                memory_required_gb: null,
              }),
              row({
                catalog_id: "tight",
                label: "Too tight model",
                fit: "too_tight",
              }),
            ],
          })
        )
      )
    )
    const user = userEvent.setup()
    render(<ModelCatalogPage />)

    const actions = await screen.findAllByRole("button", {
      name: "Download",
    })
    expect(screen.getByText("More models")).toBeTruthy()
    expect(screen.getByText("May be slow")).toBeTruthy()
    expect(screen.getByText("Doesn't fit")).toBeTruthy()
    expect(screen.queryByText("Parameters")).toBeNull()
    expect((actions[1] as HTMLButtonElement).disabled).toBe(true)
    await user.click(actions[0])
    const dialog = screen.getByRole("alertdialog", {
      name: "Use a marginal-fit model?",
    })
    expect(dialog).toBeTruthy()
    expect(dialog.className).toContain("select-none")
  })

  it("uses content-width separators between populated catalog sections", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          catalog({
            explore: [row({ catalog_id: "explore", label: "Explore model" })],
            installed: [
              row({
                catalog_id: "installed",
                label: "Installed model",
                installed: true,
              }),
            ],
          })
        )
      )
    )

    render(<ModelCatalogPage installedFirst />)

    await screen.findByText("Installed model")
    const separators = document.querySelectorAll('[data-slot="separator"]')
    expect(separators).toHaveLength(2)
    for (const separator of separators) {
      expect(separator.className).toContain("data-horizontal:w-full")
      expect(separator.className).toContain("my-4")
      expect(separator.className).not.toContain("mx-3")
    }
  })

  it("shows install failures as a toast instead of inside the model row", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/llm/catalog") {
          return Response.json(catalog())
        }
        return Response.json(
          { detail: "The model could not be installed. Retry the download." },
          { status: 500 }
        )
      })
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
    await user.click(await screen.findByRole("button", { name: "Download" }))

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "The model could not be installed. Retry the download.",
        { id: "model-install-error" }
      )
    )
    expect(
      screen.queryByText("The model could not be installed. Retry the download.")
    ).toBeNull()
  })

  it("rescans through the explicit refresh endpoint", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      void input
      return Response.json(catalog())
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ModelCatalogPage />)

    await user.click(
      await screen.findByRole("button", { name: "Rescan hardware" })
    )
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path]) => path === "/llm/catalog?refresh=true"
        )
      ).toBe(true)
    )
  })

  it("keeps installed controls when recommendations are degraded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          catalog({
            hardware: null,
            recommended: [],
            installed: [
              row({
                catalog_id: "installed",
                installed: true,
                can_install: false,
              }),
            ],
            warnings: [
              {
                code: "missing",
                message: "Hardware recommendations are unavailable.",
              },
            ],
          })
        )
      )
    )

    render(<ModelCatalogPage />)

    expect(
      await screen.findByText("Hardware recommendations are unavailable.")
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Use" })).toBeTruthy()
  })

  it("confirms deletion and reports when the selected model was removed", async () => {
    const onModelUnavailable = vi.fn()
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/llm/catalog") {
        return Response.json(
          catalog({
            recommended: [],
            installed: [
              row({
                installed: true,
                selected: true,
                can_delete: true,
                label: "Qwen 3 8B",
              }),
            ],
          })
        )
      }
      if (path === "/llm/providers/ollama/models/qwen3%3A8b") {
        return Response.json({
          name: "qwen3:8b",
          selection_cleared: true,
        })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(
      <ModelCatalogPage
        allowDelete
        onModelUnavailable={onModelUnavailable}
      />
    )
    const deleteButton = await screen.findByRole("button", {
      name: "Delete Qwen 3 8B",
    })
    expect(deleteButton.getAttribute("data-variant")).toBe("destructive")
    await user.click(deleteButton)
    expect(
      screen.getByText(
        "This is your current model. Deleting it will require you to choose another model."
      )
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete model" }))

    await waitFor(() => expect(onModelUnavailable).toHaveBeenCalledOnce())
  })

  it("cancels an in-flight install without selecting it", async () => {
    const onSelected = vi.fn()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/llm/catalog") {
          return Response.json(catalog())
        }
        const body = new ReadableStream<Uint8Array>({
          start(controller) {
            init?.signal?.addEventListener(
              "abort",
              () =>
                controller.error(
                  new DOMException("Installation cancelled", "AbortError")
                ),
              { once: true }
            )
          },
        })
        return new Response(body)
      })
    )
    const user = userEvent.setup()
    render(<ModelCatalogPage onSelected={onSelected} />)

    await user.click(await screen.findByRole("button", { name: "Download" }))
    await user.click(await screen.findByRole("button", { name: "Cancel" }))

    await waitFor(() =>
      expect(toast.info).toHaveBeenCalledWith(
        "Installation cancelled. You can retry.",
        { id: "model-install-cancelled" }
      )
    )
    expect(
      screen.queryByText("Installation cancelled. You can retry.")
    ).toBeNull()
    expect(onSelected).not.toHaveBeenCalled()
  })
})
