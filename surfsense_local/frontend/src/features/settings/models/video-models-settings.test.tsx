import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { VideoModelsSettings } from "./video-models-settings"

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
  slots: string[],
  installedAs: string
) => ({
  id,
  source: "local",
  origin: "curated",
  name,
  family: name,
  types: slots,
  known: true,
  approximate: false,
  selectable_for: slots,
  support: { context: null, reads_images: false, tools: null, reasoning: null },
  runnable: true,
  not_runnable_reason: null,
  default_quantization: "Q8_0",
  recommended: false,
  engine: "sdcpp",
  lead: { quantization: "Q8_0", why: "installed" },
  builds: [
    {
      catalog_id: `opaque-${id}`,
      quantization: "Q8_0",
      footprint_bytes: 5_440_000_000,
      files: [],
      fit: null,
      badge: null,
      can_install: true,
      installed_as: installedAs,
      selected: false,
      selected_for: [],
      recommended: false,
      reads_images: false,
      projector_checked: false,
      bundled: false,
    },
  ],
})

const wan = onDisk(
  "wan2.1-t2v-1.3b",
  "Wan2.1 T2V 1.3B",
  ["video_gen"],
  "Wan2.1-T2V-1.3B-Q8_0"
)
const klein = onDisk(
  "flux2-klein-4b",
  "FLUX.2 klein 4B",
  ["image_gen", "image_edit"],
  "flux-2-klein-4b-Q4_0"
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
    if (path === "/llm/selection/video_gen" && init?.method === "PUT") {
      return Response.json({
        model_type: "video_gen",
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

describe("video model settings", () => {
  it("offers the video models, and no image model", async () => {
    const fetchMock = serving([wan, klein])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<VideoModelsSettings onModelUnavailable={() => undefined} />)

    expect(
      await screen.findByRole("heading", { name: "Video generation models" })
    ).toBeTruthy()
    await user.click(
      await screen.findByRole("button", { name: "Use Wan2.1 T2V 1.3B" })
    )
    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/video_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "sdcpp",
        connection_id: null,
        name: "Wan2.1-T2V-1.3B-Q8_0",
      })
    })
    expect(screen.queryByText(/FLUX.2 klein/)).toBeNull()
  })
})
