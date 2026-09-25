import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ImageEditModelsSettings } from "./image-edit-models-settings"

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

/** An sd.cpp row on disk, filling the slots its entry names. */
const onDisk = (
  id: string,
  name: string,
  selectableFor: string[],
  build: Record<string, unknown>
) => ({
  id,
  source: "local",
  origin: "curated",
  name,
  family: name,
  types: selectableFor,
  known: true,
  approximate: false,
  selectable_for: selectableFor,
  support: { context: null, reads_images: false, tools: null, reasoning: null },
  runnable: true,
  not_runnable_reason: null,
  default_quantization: "Q4_0",
  recommended: false,
  engine: "sdcpp",
  lead: { quantization: "Q4_0", why: "installed" },
  builds: [
    {
      catalog_id: `opaque-${id}`,
      quantization: "Q4_0",
      footprint_bytes: 5_170_000_000,
      files: [],
      fit: null,
      badge: null,
      can_install: true,
      selected: false,
      selected_for: [],
      recommended: false,
      reads_images: false,
      projector_checked: false,
      bundled: false,
      ...build,
    },
  ],
})

// FLUX.2 klein makes images and edits them, and is in use for images; SD 1.5
// only makes them.
const klein = onDisk(
  "flux2-klein-4b",
  "FLUX.2 klein 4B",
  ["image_gen", "image_edit"],
  {
    installed_as: "flux-2-klein-4b-Q4_0",
    selected: true,
    selected_for: ["image_gen"],
  }
)
const sd15 = onDisk(
  "stable-diffusion-1.5",
  "Stable Diffusion 1.5",
  ["image_gen"],
  {
    installed_as: "v1-5-pruned_Q4_0",
  }
)

function serving(rows: unknown[]) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/catalog/local") {
      return Response.json({
        budget,
        gpu_status: "present",
        rows,
        recommended_id: null,
      })
    }
    if (path === "/llm/selection/image_edit" && init?.method === "PUT") {
      return Response.json({
        model_type: "image_edit",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-09-25T00:00:00Z",
      })
    }
    if (path.startsWith("/llm/selection/")) {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json([])
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("image editing model settings", () => {
  it("offers the image models that edit, for editing", async () => {
    // In use for images is not in use for editing: Use chooses it here too,
    // with nothing more to download.
    const fetchMock = serving([klein, sd15])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ImageEditModelsSettings onModelUnavailable={() => undefined} />)

    expect(
      await screen.findByRole("heading", { name: "Image editing models" })
    ).toBeTruthy()
    await user.click(
      await screen.findByRole("button", { name: "Use FLUX.2 klein 4B" })
    )
    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/image_edit" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "sdcpp",
        connection_id: null,
        name: "flux-2-klein-4b-Q4_0",
      })
    })
    expect(screen.queryByText(/Stable Diffusion 1.5/)).toBeNull()
  })
})
