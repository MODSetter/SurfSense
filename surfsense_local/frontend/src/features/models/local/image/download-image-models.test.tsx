import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { LocalBuild, LocalRow, ModelCatalog } from "../chat/api"
import { DownloadImageModels } from "./download-image-models"

const budget = {
  device_total_bytes: 16_000_000_000,
  device_free_bytes: 14_000_000_000,
  usable_vram_bytes: 12_900_000_000,
  fit_reserve_bytes: 1_073_741_824,
  ram_available_bytes: 16_000_000_000,
  uma: true,
  has_gpu: true,
}

const build = (overrides: Partial<LocalBuild> = {}): LocalBuild => ({
  catalog_id: "opaque-sdxl-turbo",
  quantization: "Q4_0",
  footprint_bytes: 2_000_000_000,
  files: [],
  fit: null,
  badge: null,
  can_install: true,
  installed_as: null,
  selected: false,
  recommended: false,
  reads_images: false,
  projector_checked: false,
  bundled: false,
  ...overrides,
})

/** sd.cpp's catalog row: one build, no fit estimate. */
const row = (
  overrides: Partial<LocalRow> = {},
  builds: LocalBuild[] = [build()]
): LocalRow => ({
  id: "sdxl-turbo",
  source: "local",
  origin: "curated",
  name: "SDXL Turbo",
  family: "Stable Diffusion",
  types: ["image_gen"],
  known: true,
  approximate: false,
  selectable_for: ["image_gen"],
  support: { context: null, reads_images: false, tools: null, reasoning: null },
  runnable: true,
  not_runnable_reason: null,
  builds,
  default_quantization: "Q4_0",
  recommended: false,
  engine: "sdcpp",
  lead: { quantization: builds[0]?.quantization ?? "", why: "default" },
  ...overrides,
})

const catalog = (overrides: Partial<ModelCatalog> = {}): ModelCatalog => ({
  budget,
  gpu_status: "present",
  rows: [row()],
  recommended_id: null,
  ...overrides,
})

function serving(
  data: ModelCatalog,
  extra: (path: string, init?: RequestInit) => Response | null = () => null
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/catalog/local") return Response.json(data)
    return (
      extra(path, init) ??
      Response.json({ detail: "not found" }, { status: 404 })
    )
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("DownloadImageModels", () => {
  it("deletes a downloaded image model from the Add model page, like the settings list", async () => {
    const fetchMock = serving(
      catalog({
        rows: [row({}, [build({ installed_as: "sdxl-turbo-q4_0" })])],
      }),
      (path, init) =>
        path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
          ? Response.json({ name: "sdxl-turbo-q4_0", selection_cleared: false })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<DownloadImageModels />)
    await user.click(
      await screen.findByRole("button", { name: "Delete SDXL Turbo" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Delete model" })
    )

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("deletes the image model in use from the Add model page too", async () => {
    const fetchMock = serving(
      catalog({
        rows: [
          row({}, [build({ installed_as: "sdxl-turbo-q4_0", selected: true })]),
        ],
      }),
      (path, init) =>
        path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
          ? Response.json({ name: "sdxl-turbo-q4_0", selection_cleared: true })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<DownloadImageModels />)
    await user.click(
      await screen.findByRole("button", { name: "Delete SDXL Turbo" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Delete model" })
    )

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })
})
