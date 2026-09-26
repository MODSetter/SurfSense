import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { fakeInstallApi } from "@/features/models/local/installs/fake-install-api"
import { render } from "@/test-utils"

import { AudioModelsSettings } from "./audio-models-settings"

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

/** audio.cpp's catalog row: no fit estimate, and what voicing takes instead. */
const audioRow = (
  overrides: Record<string, unknown> = {},
  build: Record<string, unknown> = {}
) => ({
  id: "kokoro-82m",
  source: "local",
  origin: "curated",
  name: "Kokoro 82M",
  family: "Kokoro",
  types: ["audio_gen"],
  known: true,
  approximate: false,
  selectable_for: ["audio_gen"],
  support: { context: null, reads_images: false, tools: null, reasoning: null },
  runnable: true,
  not_runnable_reason: null,
  default_quantization: "Q8_0",
  recommended: false,
  engine: "audiocpp",
  lead: { quantization: "Q8_0", why: "default" },
  voicing: {
    peak_mb: 1421,
    voice_count: 46,
    languages: ["en-GB", "en-US", "es", "fr", "hi", "it", "pt-BR", "zh"],
  },
  builds: [
    {
      catalog_id: "opaque-kokoro",
      quantization: "Q8_0",
      footprint_bytes: 189_549_408,
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
  ...overrides,
})

const kittenRow = audioRow(
  {
    id: "kitten-tts-mini-0.8",
    name: "KittenTTS Mini 0.8",
    family: "KittenTTS",
    default_quantization: "orig",
    lead: { quantization: "orig", why: "default" },
    voicing: { peak_mb: 1023, voice_count: 8, languages: ["en"] },
  },
  { catalog_id: "opaque-kitten", quantization: "orig" }
)

const chatRow = {
  ...audioRow({}, { installed_as: "Qwen3-8B-Q4_K_M" }),
  id: "qwen3-8b",
  name: "Qwen3 8B",
  family: "Qwen3",
  types: ["text_gen"],
  selectable_for: ["text_gen"],
  engine: "llamacpp",
  voicing: null,
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
    if (path === "/llm/selection/audio_gen" && init?.method === "PUT") {
      return Response.json({
        model_type: "audio_gen",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-09-24T00:00:00Z",
      })
    }
    if (path === "/llm/selection/audio_gen") {
      return Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json([])
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("audio model settings", () => {
  it("says audio models cannot run where no audio runtime shipped", async () => {
    // No audio.cpp staged: the catalog carries chat rows and no audio rows.
    vi.stubGlobal("fetch", serving([chatRow]))
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    expect(await screen.findByText("No audio model yet")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Add model" }))

    expect(
      screen.getByRole("heading", { name: "Add an audio model" })
    ).toBeTruthy()
    expect(
      await screen.findByText("Audio models cannot run on this computer")
    ).toBeTruthy()
  })

  it("describes each model by what voicing takes and what it speaks", async () => {
    vi.stubGlobal("fetch", serving([audioRow(), kittenRow]))
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))

    // Separated by the icon set's dot, as chat's cards are, not a typed "·".
    const facts = (text: string) => {
      const line = screen.getByText(text).parentElement
      expect(line?.textContent).not.toContain("·")
      return [...(line?.querySelectorAll(":scope > span") ?? [])].map(
        (part) => part.textContent
      )
    }
    await screen.findByText("46 voices")
    expect(facts("46 voices")).toEqual([
      "Q8_0",
      "190 MB",
      "1.4 GB while voicing",
      "46 voices",
      "8 languages",
    ])
    // One language is named rather than counted.
    expect(facts("8 voices").at(-1)).toBe("English")
  })

  it("uses a downloaded audio model through audio.cpp", async () => {
    const fetchMock = serving([
      audioRow({}, { installed_as: "kokoro-82m-q8_0" }),
      chatRow,
    ])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(
      await screen.findByRole("button", { name: "Use Kokoro 82M" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/audio_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "audiocpp",
        connection_id: null,
        name: "kokoro-82m-q8_0",
      })
    })
    expect(screen.queryByText(/Qwen3 8B/)).toBeNull()
  })

  it("deletes the audio model podcasts voice with, after a warning", async () => {
    const fetchMock = serving(
      [audioRow({}, { installed_as: "kokoro-82m-q8_0", selected: true })],
      (path, init) =>
        path === "/llm/models/kokoro-82m-q8_0" && init?.method === "DELETE"
          ? Response.json({
              name: "kokoro-82m-q8_0",
              selection_cleared: true,
            })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(
      await screen.findByRole("button", { name: "Delete Kokoro 82M" })
    )
    expect(await screen.findByText(/This is your current model/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete model" }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/kokoro-82m-q8_0" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("marks the audio model in use on the Add model page, as chat and image do", async () => {
    vi.stubGlobal(
      "fetch",
      serving([
        audioRow({}, { installed_as: "kokoro-82m-q8_0", selected: true }),
      ])
    )
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))

    const inUse = await screen.findByRole("button", { name: "In use" })
    expect(inUse.hasAttribute("disabled")).toBe(true)
    expect(
      screen.getByRole("button", { name: "Delete Kokoro 82M" })
    ).toBeTruthy()
  })

  it("uses a downloaded audio model from the Add model page", async () => {
    const fetchMock = serving([
      audioRow({}, { installed_as: "kokoro-82m-q8_0" }),
    ])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Use Kokoro 82M Q8_0" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/audio_gen" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "audiocpp",
        connection_id: null,
        name: "kokoro-82m-q8_0",
      })
    })
  })

  it("deletes a downloaded audio model from the Add model page", async () => {
    const fetchMock = serving(
      [audioRow({}, { installed_as: "kokoro-82m-q8_0" })],
      (path, init) =>
        path === "/llm/models/kokoro-82m-q8_0" && init?.method === "DELETE"
          ? Response.json({
              name: "kokoro-82m-q8_0",
              selection_cleared: false,
            })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Delete Kokoro 82M" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Delete model" })
    )

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/kokoro-82m-q8_0" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("names the phase while it downloads, as chat and image do", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-kokoro": ["audio_gen"] },
    })
    vi.stubGlobal("fetch", serving([audioRow()], installs.handle))
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Download Kokoro 82M Q8_0" })
    )

    installs.move({
      type: "downloading",
      message: "Downloading",
      completed: 95_000_000,
      total: 190_000_000,
    })

    const button = await screen.findByRole("button", {
      name: "Download Kokoro 82M Q8_0",
    })
    await waitFor(() => expect(button.textContent).toBe("Downloading…"))
    expect(screen.getAllByText("50%").length).toBeGreaterThan(0)

    installs.complete()
    await waitFor(() => expect(button.textContent).toBe("Download"))
  })

  it("downloads through the catalog without selecting", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving([audioRow()], installs.handle))
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Download Kokoro 82M Q8_0" })
    )

    await waitFor(() =>
      expect(installs.started).toEqual([
        { catalog_id: "opaque-kokoro", select: false },
      ])
    )
  })
})
