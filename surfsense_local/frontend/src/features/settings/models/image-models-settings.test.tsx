import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { fakeInstallApi } from "@/features/models/local/installs/fake-install-api"

import { ImageModelsSettings } from "./image-models-settings"
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

/** sd.cpp's catalog row: one build, no fit estimate. */
const imageRow = (build: Record<string, unknown> = {}) => ({
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
  default_quantization: "Q4_0",
  recommended: false,
  engine: "sdcpp",
  lead: { quantization: "Q4_0", why: "default" },
  builds: [
    {
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
      ...build,
    },
  ],
})

const chatRow = {
  ...imageRow({ installed_as: "Qwen3-8B-Q4_K_M" }),
  id: "qwen3-8b",
  name: "Qwen3 8B",
  family: "Qwen3",
  types: ["text_gen"],
  selectable_for: ["text_gen"],
  engine: "llamacpp",
}

function serving(
  rows: unknown[],
  extra: (path: string, init?: RequestInit) => Response | null = () => null
) {
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
    if (path === "/llm/selection/image_gen" && init?.method === "PUT") {
      return Response.json({
        model_type: "image_gen",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-09-24T00:00:00Z",
      })
    }
    if (path === "/llm/selection/image_gen") {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json([])
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("image model settings", () => {
  it("keeps the chat layout where no local image runtime shipped", async () => {
    // No sd-server staged: the catalog carries chat rows and no image rows.
    vi.stubGlobal("fetch", serving([chatRow]))
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

    expect(await screen.findByText("No image model yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Add model" }))

    // The same page as chat: the section says why nothing runs here.
    expect(
      screen.getByRole("heading", { name: "Add an image model" })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Connect" })).toBeTruthy()
    expect(
      await screen.findByText("Image models cannot run on this computer")
    ).toBeTruthy()
  })

  it("uses a downloaded image model through the local image runtime", async () => {
    const fetchMock = serving([
      imageRow({ installed_as: "sdxl-turbo-q4_0" }),
      chatRow,
    ])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)
    await user.click(
      await screen.findByRole("button", { name: "Use SDXL Turbo" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/image_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "sdcpp",
        connection_id: null,
        name: "sdxl-turbo-q4_0",
      })
    })
    // A chat model on disk is the chat page's, not this one's.
    expect(screen.queryByText(/Qwen3 8B/)).toBeNull()
  })

  it("deletes the image model in use, like chat", async () => {
    const fetchMock = serving(
      [imageRow({ installed_as: "sdxl-turbo-q4_0", selected: true })],
      (path, init) =>
        path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
          ? Response.json({ name: "sdxl-turbo-q4_0", selection_cleared: true })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

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

  it("deletes an image model by the name it has on disk", async () => {
    const fetchMock = serving(
      [imageRow({ installed_as: "sdxl-turbo-q4_0" })],
      (path, init) =>
        path === "/llm/models/sdxl-turbo-q4_0" && init?.method === "DELETE"
          ? Response.json({ name: "sdxl-turbo-q4_0", selection_cleared: false })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

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

  it("downloads through the catalog without selecting", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-sdxl-turbo": ["image_gen"] },
    })
    const fetchMock = serving([imageRow()], installs.handle)
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Download SDXL Turbo Q4_0" })
    )

    await waitFor(() =>
      expect(installs.started).toEqual([
        { catalog_id: "opaque-sdxl-turbo", select: false },
      ])
    )
    expect(
      fetchMock.mock.calls.some(([path]) =>
        String(path).startsWith("/llm/image/local")
      )
    ).toBe(false)
  })

  it("names the phase while it downloads and cancels, like chat", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-sdxl-turbo": ["image_gen"] },
    })
    vi.stubGlobal("fetch", serving([imageRow()], installs.handle))
    const user = userEvent.setup()
    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Download SDXL Turbo Q4_0" })
    )
    installs.move({
      type: "downloading",
      completed: 1_000_000_000,
      total: 2_000_000_000,
    })

    expect(await screen.findAllByText("Downloading…")).not.toHaveLength(0)
    expect(screen.getAllByText("1 GB of 2 GB")).not.toHaveLength(0)

    await user.click(screen.getAllByRole("button", { name: "Cancel" })[0])
    expect(
      await screen.findByRole("button", { name: "Download SDXL Turbo Q4_0" })
    ).toBeTruthy()
  })

  it("shows only downloads its own slot can use, wherever they started", async () => {
    // A video download started on the video page, before this one opened.
    const installs = fakeInstallApi({
      running: [
        {
          id: "job-video",
          catalog_id: "opaque-wan",
          label: "Wan 2.2 Q4_0",
          model_types: ["video_gen"],
          select: false,
          model_type: null,
          event: { type: "downloading", completed: 1, total: 2 },
        },
      ],
    })
    vi.stubGlobal(
      "fetch",
      serving([imageRow({ installed_as: "sdxl-turbo-q4_0" })], installs.handle)
    )

    render(<ImageModelsSettings onModelUnavailable={() => undefined} />)
    await screen.findByRole("button", { name: "Use SDXL Turbo" })
    expect(screen.queryByText("Wan 2.2 Q4_0")).toBeNull()
    cleanup()

    render(<VideoModelsSettings onModelUnavailable={() => undefined} />)
    expect(await screen.findByText("Wan 2.2 Q4_0")).toBeTruthy()
    expect(screen.getByRole("progressbar")).toBeTruthy()
  })
})
