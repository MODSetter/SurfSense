import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"
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
  initial: { source: "server" | "saved"; voices: string[] },
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
        voices_page: "https://openrouter.ai/seed-audio",
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
