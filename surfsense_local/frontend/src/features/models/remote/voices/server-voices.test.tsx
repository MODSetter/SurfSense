import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ServerVoices } from "./server-voices"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const URL_ = "/llm/selection/audio_gen/voices"

/** The audio selection's voices, as the backend keeps them. */
function serving(
  initial: { source: "server" | "published" | "saved"; voices: string[] },
  refused: string[] = [],
  sent: unknown[] = []
) {
  let voices = [...initial.voices]
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === URL_ && (init?.method ?? "GET") === "GET") {
      return Response.json({
        connection_id: 1,
        model: "seed-audio",
        source: initial.source,
        voices,
        added: voices.filter(
          (voice) =>
            initial.source === "saved" ||
            (initial.source === "published" && !initial.voices.includes(voice))
        ),
        voices_page:
          initial.source === "saved"
            ? "https://openrouter.ai/seed-audio"
            : null,
      })
    }
    if (path === URL_ && init?.method === "POST") {
      sent.push(JSON.parse(String(init.body)))
      const voice = JSON.parse(String(init.body)).voice as string
      if (refused.includes(voice)) {
        return Response.json(
          { detail: "the server could not voice turn 1 of 1: unknown voice" },
          { status: 502 }
        )
      }
      voices = [...voices, voice]
      return new Response(null, { status: 201 })
    }
    if (path.startsWith(`${URL_}?voice=`) && init?.method === "DELETE") {
      const voice = decodeURIComponent(path.split("=")[1])
      voices = voices.filter((kept) => kept !== voice)
      return new Response(null, { status: 204 })
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

describe("a server audio model's voices", () => {
  it("shows the voices the server lists, with nothing to add", async () => {
    vi.stubGlobal("fetch", serving({ source: "server", voices: ["af_heart"] }))
    render(<ServerVoices />)

    expect(await screen.findByText("Listed by the server")).toBeTruthy()
    expect(screen.getByText("af_heart")).toBeTruthy()
    expect(screen.queryByRole("textbox", { name: "Voice ID" })).toBeNull()
  })

  it("offers a model's published voices, and adds and removes only others", async () => {
    vi.stubGlobal(
      "fetch",
      serving({ source: "published", voices: ["sarah", "george"] })
    )
    const user = userEvent.setup()
    render(<ServerVoices />)

    expect(await screen.findByText("sarah")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Remove sarah" })).toBeNull()
    expect(screen.queryByRole("link")).toBeNull()

    await user.type(screen.getByRole("textbox", { name: "Voice ID" }), "OZ0L6")
    await user.click(screen.getByRole("button", { name: "Add and test" }))

    await user.click(
      await screen.findByRole("button", { name: "Remove OZ0L6" })
    )
    await waitFor(() => expect(screen.queryByText("OZ0L6")).toBeNull())
    expect(screen.getByText("george")).toBeTruthy()
  })

  it("keeps a voice only once the server has voiced it, and removes it", async () => {
    const sent: unknown[] = []
    vi.stubGlobal(
      "fetch",
      serving({ source: "saved", voices: [] }, ["nobody"], sent)
    )
    const user = userEvent.setup()
    render(<ServerVoices />)

    expect(
      await screen.findByText(/This server doesn’t list its voices/)
    ).toBeTruthy()
    expect(
      screen
        .getByRole("link", { name: "See this model’s voices" })
        .getAttribute("href")
    ).toBe("https://openrouter.ai/seed-audio")

    const field = screen.getByRole("textbox", { name: "Voice ID" })
    await user.type(field, "nobody")
    await user.click(screen.getByRole("button", { name: "Add and test" }))
    expect(await screen.findByText(/unknown voice/)).toBeTruthy()
    expect(screen.queryByRole("listitem")).toBeNull()

    await user.clear(field)
    await user.type(field, "en_paul_neutral")
    await user.click(screen.getByRole("button", { name: "Add and test" }))
    const row = await screen.findByRole("listitem")
    // Heard saying a line in the interface's language.
    expect(sent.at(-1)).toEqual({
      voice: "en_paul_neutral",
      text: "Hello. This is how your podcasts will sound.",
    })
    expect(within(row).getByText("en_paul_neutral")).toBeTruthy()
    expect((field as HTMLInputElement).value).toBe("")

    await user.click(
      within(row).getByRole("button", { name: "Remove en_paul_neutral" })
    )
    await vi.waitFor(() => expect(screen.queryByRole("listitem")).toBeNull())
  })

  it("opens the model's voices page in the browser, not in the app", async () => {
    vi.stubGlobal("fetch", serving({ source: "saved", voices: [] }))
    const openExternal = vi.fn(async () => undefined)
    vi.stubGlobal("surfsense", { openExternal })
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(
      await screen.findByRole("link", { name: "See this model’s voices" })
    )

    expect(openExternal).toHaveBeenCalledWith(
      "https://openrouter.ai/seed-audio"
    )
  })
})

/** The element the app plays through, which jsdom cannot: records and is driven. */
class FakeAudio {
  static made: FakeAudio[] = []
  static refuse = false
  src = ""
  paused = true
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  error: { message: string } | null = null
  constructor() {
    FakeAudio.made.push(this)
  }
  play() {
    if (FakeAudio.refuse) return Promise.reject(new Error("playback blocked"))
    this.paused = false
    return Promise.resolve()
  }
  pause() {
    this.paused = true
  }
  finish() {
    this.paused = true
    this.onended?.()
  }
}

/** Two listed voices, with a speech test the test can refuse or hold open. */
function hearing(refused: string[] = []) {
  FakeAudio.made = []
  FakeAudio.refuse = false
  vi.stubGlobal("Audio", FakeAudio)
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: () => "blob:clip",
      revokeObjectURL: () => {},
    })
  )
  const voices = serving({ source: "published", voices: ["sarah", "george"] })
  const tests: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (!String(input).endsWith("/speech-test")) return voices(input, init)
      const { voice } = JSON.parse(String(init?.body)) as { voice: string }
      tests.push(voice)
      return refused.includes(voice)
        ? Response.json({ detail: `refused ${voice}` }, { status: 502 })
        : new Response(new Blob(["clip"], { type: "audio/wav" }))
    })
  )
  return tests
}

describe("hearing a listed voice", () => {
  it("plays with no player on the page, and offers Stop until told to", async () => {
    hearing()
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    const stop = await screen.findByRole("button", { name: "Stop sarah" })

    expect(document.querySelector("audio")).toBeNull()
    expect(FakeAudio.made[0].paused).toBe(false)

    await user.click(stop)

    expect(FakeAudio.made[0].paused).toBe(true)
    expect(
      await screen.findByRole("button", { name: "Play sarah" })
    ).toBeTruthy()
  })

  it("goes back to Play when the clip ends", async () => {
    hearing()
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    await screen.findByRole("button", { name: "Stop sarah" })
    act(() => FakeAudio.made[0].finish())

    expect(
      await screen.findByRole("button", { name: "Play sarah" })
    ).toBeTruthy()
  })

  it("plays one voice at a time", async () => {
    hearing()
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    await screen.findByRole("button", { name: "Stop sarah" })
    await user.click(screen.getByRole("button", { name: "Play george" }))
    await screen.findByRole("button", { name: "Stop george" })

    expect(FakeAudio.made[0].paused).toBe(true)
    expect(screen.getByRole("button", { name: "Play sarah" })).toBeTruthy()
  })

  it("asks the server once per voice, since every request may be billed", async () => {
    const tests = hearing()
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    await user.click(await screen.findByRole("button", { name: "Stop sarah" }))
    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    await screen.findByRole("button", { name: "Stop sarah" })

    expect(tests).toEqual(["sarah"])
  })

  it("says why under the voice the server refused, and offers it again", async () => {
    hearing(["sarah"])
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))

    const row = (await screen.findByText("refused sarah")).closest("li")
    expect(
      within(row!).getByRole("button", { name: "Play sarah" })
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Play george" })).toBeTruthy()
  })

  it("says so when playing fails once started, rather than stay on Stop", async () => {
    hearing()
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))
    await screen.findByRole("button", { name: "Stop sarah" })
    act(() => {
      const [element] = FakeAudio.made
      element.error = { message: "no audio device" }
      element.onerror?.()
    })

    expect(await screen.findByText("no audio device")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Play sarah" })).toBeTruthy()
  })

  it("says so when the browser will not play it", async () => {
    hearing()
    FakeAudio.refuse = true
    const user = userEvent.setup()
    render(<ServerVoices />)

    await user.click(await screen.findByRole("button", { name: "Play sarah" }))

    expect(await screen.findByText("playback blocked")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Play sarah" })).toBeTruthy()
  })
})
