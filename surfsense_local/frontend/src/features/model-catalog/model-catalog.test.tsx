import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"
import { ModelCatalogPage } from "./model-catalog-page"
import { parseNdjson, type CatalogRow, type ModelCatalog } from "./api"

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
    expect(screen.queryByText("Parameters")).toBeNull()
    expect((actions[1] as HTMLButtonElement).disabled).toBe(true)
    await user.click(actions[0])
    expect(
      screen.getByRole("alertdialog", { name: "Use a marginal-fit model?" })
    ).toBeTruthy()
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

    expect(
      await screen.findByText("Installation cancelled. You can retry.")
    ).toBeTruthy()
    expect(onSelected).not.toHaveBeenCalled()
  })
})
