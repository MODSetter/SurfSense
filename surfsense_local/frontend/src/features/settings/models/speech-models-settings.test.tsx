import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { fakeInstallApi } from "@/features/models/local/installs/fake-install-api"
import {
  fakeSpeechRow,
  NEMOTRON_LANGUAGES,
  SPEECH_IN_USE,
  SPEECH_INSTALLED,
} from "@/features/models/local/transcription/fake-speech-rows"
import { render } from "@/test-utils"

import { SpeechModelsSettings } from "./speech-models-settings"

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

const voiceRow = {
  ...fakeSpeechRow(),
  id: "kokoro-82m",
  name: "Kokoro 82M",
  types: ["audio_gen"],
  selectable_for: ["audio_gen"],
  transcription: null,
  voicing: { peak_mb: 1421, voice_count: 46, languages: ["en-US"] },
}

type Extra = (path: string, init?: RequestInit) => Response | null

function serving(rows: unknown[], extra: Extra = () => null) {
  const selected = rows.some((row) =>
    (row as ReturnType<typeof fakeSpeechRow>).builds.some(
      (build) => (build as { selected_for?: string[] }).selected_for
    )
  )
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
    if (path === "/llm/selection/speech_to_text" && init?.method === "PUT") {
      return Response.json({
        model_type: "speech_to_text",
        ...JSON.parse(String(init.body)),
        updated_at: "2026-10-14T00:00:00Z",
      })
    }
    if (path === "/llm/selection/speech_to_text") {
      return selected
        ? Response.json({
            model_type: "speech_to_text",
            provider: "audiocpp",
            connection_id: null,
            name: SPEECH_IN_USE.installed_as,
            updated_at: "2026-10-14T00:00:00Z",
          })
        : Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/connections") return Response.json([])
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

const renderSettings = () => render(<SpeechModelsSettings />)

describe("speech recognition settings", () => {
  it("offers no server, since only this computer recognises speech", async () => {
    // No audio.cpp that transcribes: the catalog carries no speech rows.
    vi.stubGlobal("fetch", serving([voiceRow]))
    const user = userEvent.setup()
    renderSettings()

    expect(
      await screen.findByText("No speech recognition model yet")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Add model" }))

    expect(
      screen.getByRole("heading", {
        name: "Add a speech recognition model",
      })
    ).toBeTruthy()
    expect(
      await screen.findByText(
        "Speech recognition models cannot run on this computer"
      )
    ).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Connect" })).toBeNull()
    expect(screen.queryByText(/Kokoro/)).toBeNull()
  })

  it("offers no ChatGPT plan either, even one that says it serves the slot", async () => {
    vi.stubGlobal(
      "fetch",
      serving([], (path) =>
        path === "/llm/connections/chatgpt"
          ? Response.json({ serves: ["text_gen", "speech_to_text"], hosts: [] })
          : null
      )
    )
    const user = userEvent.setup()
    renderSettings()

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    expect(
      await screen.findByText(
        "Speech recognition models cannot run on this computer"
      )
    ).toBeTruthy()
    expect(
      screen.queryByRole("region", { name: "Use your ChatGPT plan" })
    ).toBeNull()
    expect(screen.queryByRole("region", { name: "Use a server" })).toBeNull()
  })

  it("says the models could not load, not that this computer cannot run one", async () => {
    vi.stubGlobal(
      "fetch",
      serving([], (path) =>
        path === "/llm/catalog/local"
          ? Response.json({ detail: "catalog failed" }, { status: 500 })
          : null
      )
    )
    renderSettings()

    expect(
      await screen.findByText("Could not load model settings")
    ).toBeTruthy()
    expect(screen.queryByText("This computer can’t run one.")).toBeNull()
  })

  it("shows an empty slot without waiting on servers it never offers", async () => {
    vi.stubGlobal(
      "fetch",
      serving([fakeSpeechRow()], (path) =>
        path === "/llm/connections"
          ? Response.json({ detail: "connections failed" }, { status: 500 })
          : null
      )
    )
    renderSettings()

    expect(
      await screen.findByText("No speech recognition model yet")
    ).toBeTruthy()
    expect(
      screen.getByText("Download one to run on this computer.")
    ).toBeTruthy()
  })

  it("describes each model by what transcribing takes and what it understands", async () => {
    vi.stubGlobal("fetch", serving([fakeSpeechRow(), voiceRow]))
    const user = userEvent.setup()
    renderSettings()

    await user.click(await screen.findByRole("button", { name: "Add model" }))

    const line = (await screen.findByText("Detects the language")).parentElement
    expect(
      [...(line?.querySelectorAll(":scope > span") ?? [])].map(
        (part) => part.textContent
      )
    ).toEqual(["Q8_0", "931 MB", "Detects the language"])

    // Counted, then named in the interface's language on request.
    const count = screen.getByRole("button", { name: "26 languages" })
    expect(count.getAttribute("aria-expanded")).toBe("false")
    await user.click(count)
    expect(count.getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByText(/Arabic, Bulgarian, Chinese/)).toBeTruthy()
    expect(screen.getByText(/Norwegian Bokmål/)).toBeTruthy()
  })

  it("downloads a speech model and chooses it in one step", async () => {
    const installs = fakeInstallApi({
      modelTypes: { "opaque-nemotron": ["speech_to_text"] },
    })
    vi.stubGlobal("fetch", serving([fakeSpeechRow()], installs.handle))
    const user = userEvent.setup()
    renderSettings()

    await user.click(await screen.findByRole("button", { name: "Add model" }))
    await user.click(
      await screen.findByRole("button", {
        name: "Download Nemotron 3.5 ASR Q8_0",
      })
    )

    await waitFor(() =>
      expect(installs.started).toEqual([
        {
          catalog_id: "opaque-nemotron",
          select: true,
          model_type: "speech_to_text",
        },
      ])
    )
    installs.move({
      type: "downloading",
      message: "Downloading",
      completed: 465_300_000,
      total: 930_600_000,
    })
    expect((await screen.findAllByText("50%")).length).toBeGreaterThan(0)
  })

  it("uses a downloaded speech model through audio.cpp", async () => {
    const fetchMock = serving([fakeSpeechRow({}, SPEECH_INSTALLED)])
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderSettings()

    await user.click(
      await screen.findByRole("button", { name: "Use Nemotron 3.5 ASR" })
    )

    await waitFor(() => {
      const write = fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/llm/selection/speech_to_text" && init?.method === "PUT"
      )
      expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
        provider: "audiocpp",
        connection_id: null,
        name: "nemotron-3.5-asr-streaming-0.6b-q8_0",
      })
    })
  })

  it("deletes the speech model in use, after a warning", async () => {
    const fetchMock = serving(
      [fakeSpeechRow({}, SPEECH_IN_USE)],
      (path, init) => {
        if (path === "/llm/selection/speech_to_text/language") {
          return Response.json({
            language: "auto",
            languages: NEMOTRON_LANGUAGES,
            detects_language: true,
          })
        }
        return path === `/llm/models/${SPEECH_IN_USE.installed_as}` &&
          init?.method === "DELETE"
          ? Response.json({
              name: SPEECH_IN_USE.installed_as,
              selection_cleared: true,
            })
          : null
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderSettings()

    await user.click(
      await screen.findByRole("button", { name: "Delete Nemotron 3.5 ASR" })
    )
    expect(await screen.findByText(/This is your current model/)).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete model" }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === `/llm/models/${SPEECH_IN_USE.installed_as}` &&
            init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("offers detecting the language, then each language the model lists", async () => {
    const writes: unknown[] = []
    const fetchMock = serving(
      [fakeSpeechRow({}, SPEECH_IN_USE)],
      (path, init) => {
        if (path !== "/llm/selection/speech_to_text/language") return null
        if (init?.method === "PUT") {
          const body = JSON.parse(String(init.body)) as { language: string }
          writes.push(body)
          return Response.json({
            language: body.language,
            languages: ["ja", "en", "es"],
            detects_language: true,
          })
        }
        return Response.json({
          language: "auto",
          languages: ["ja", "en", "es"],
          detects_language: true,
        })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderSettings()

    const select = await screen.findByRole("combobox", {
      name: "Spoken language",
    })
    expect(
      within(select)
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["Detect automatically", "English", "Japanese", "Spanish"])
    expect((select as HTMLSelectElement).value).toBe("auto")

    await user.selectOptions(select, "Japanese")

    await waitFor(() => expect(writes).toEqual([{ language: "ja" }]))
    await waitFor(() => expect((select as HTMLSelectElement).value).toBe("ja"))
  })

  it("offers only the listed languages when the model cannot detect one", async () => {
    vi.stubGlobal(
      "fetch",
      serving([fakeSpeechRow({}, SPEECH_IN_USE)], (path) =>
        path === "/llm/selection/speech_to_text/language"
          ? Response.json({
              language: "de",
              languages: ["de", "fr"],
              detects_language: false,
            })
          : null
      )
    )
    renderSettings()

    const select = await screen.findByRole("combobox", {
      name: "Spoken language",
    })
    expect(
      within(select)
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["French", "German"])
    expect((select as HTMLSelectElement).value).toBe("de")
  })
})
