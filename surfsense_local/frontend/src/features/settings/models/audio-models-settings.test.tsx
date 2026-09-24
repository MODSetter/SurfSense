import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

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

function stream(lines: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const line of lines)
        controller.enqueue(new TextEncoder().encode(line))
      controller.close()
    },
  })
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

    const kokoro = await screen.findByText(/46 voices/)
    expect(kokoro.textContent).toMatch(/^Q8_0 · 190 MB · 1\.4 GB while voicing/)
    expect(kokoro.textContent).toMatch(/46 voices · 8 languages$/)
    // One language is named rather than counted.
    const kitten = screen.getByText(/8 voices/)
    expect(kitten.textContent).toMatch(/8 voices · English$/)
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

  it("will not delete the audio model podcasts voice with", async () => {
    vi.stubGlobal(
      "fetch",
      serving([
        audioRow({}, { installed_as: "kokoro-82m-q8_0", selected: true }),
      ])
    )
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    expect(await screen.findByText("Kokoro 82M")).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Delete Kokoro 82M" })
    ).toBeNull()
  })

  it("downloads through the catalog without selecting", async () => {
    const fetchMock = serving([audioRow()], (path) =>
      path === "/llm/install"
        ? new Response(
            stream([
              '{"type":"downloading","completed":1,"total":2}\n',
              '{"type":"complete","message":"Model is ready","selection":null}\n',
            ])
          )
        : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<AudioModelsSettings onModelUnavailable={() => undefined} />)

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", { name: "Download Kokoro 82M" })
    )

    await waitFor(() => {
      const install = fetchMock.mock.calls.find(
        ([path]) => path === "/llm/install"
      )
      expect(JSON.parse(String(install?.[1]?.body))).toEqual({
        catalog_id: "opaque-kokoro",
        select: false,
      })
    })
  })
})
