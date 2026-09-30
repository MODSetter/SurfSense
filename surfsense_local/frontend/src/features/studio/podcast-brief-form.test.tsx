import { useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import type { PodcastBrief, Voice } from "./api"
import { PodcastBriefForm } from "./podcast-brief-form"

const voices: Voice[] = [
  { id: "af_heart", label: "Heart", gender: "female", languages: ["en-US"] },
  { id: "am_adam", label: "Adam", gender: "male", languages: ["en-US"] },
  { id: "bf_emma", label: "Emma", gender: "female", languages: ["en-GB"] },
  { id: "pf_dora", label: "Dora", gender: "female", languages: ["pt-BR"] },
  { id: "pm_alex", label: "Alex", gender: "male", languages: ["pt-BR"] },
]

const brief: PodcastBrief = {
  language: "en-US",
  style: "conversational",
  duration: "standard",
  speakers: [
    { name: "Host", role: "host", voice: "af_heart" },
    { name: "Guest", role: "guest", voice: "am_adam" },
  ],
}

function Harness({ initial = brief }: { initial?: PodcastBrief }) {
  return <Controlled initial={initial} />
}

/** What the server sends beside a roster: the languages its voices speak. */
const spokenBy = (roster: Voice[]) => [
  ...new Set(roster.flatMap((voice) => voice.languages)),
]

function Controlled({ initial }: { initial: PodcastBrief }) {
  const [value, setValue] = useState(initial)
  return (
    <PodcastBriefForm
      brief={value}
      voices={voices}
      languages={spokenBy(voices)}
      voicesSource="local"
      voicedBy={null}
      onSetUpVoices={() => undefined}
      onChange={setValue}
    />
  )
}

afterEach(cleanup)

const value = (element: HTMLElement) =>
  (element as HTMLInputElement | HTMLSelectElement).value

// Supertonic's voices each speak every language the model does.
const multilingual: Voice[] = [
  { id: "M1", label: "M1", gender: "male", languages: ["en", "fr"] },
  { id: "F1", label: "F1", gender: "female", languages: ["en", "fr"] },
]

describe("podcast brief form", () => {
  it("opens prefilled with the proposed brief", () => {
    render(<Harness />)

    expect(value(screen.getByLabelText("Language"))).toBe("en-US")
    expect(value(screen.getByLabelText("Style"))).toBe("conversational")
    expect(
      screen
        .getByRole("button", { name: /Standard/ })
        .getAttribute("aria-pressed")
    ).toBe("true")
    const rows = screen.getAllByRole("group", { name: /Speaker \d/ })
    expect(rows).toHaveLength(2)
    expect(value(within(rows[0]).getByLabelText("Name"))).toBe("Host")
    expect(value(within(rows[0]).getByLabelText("Voice"))).toBe("af_heart")
    expect(value(within(rows[1]).getByLabelText("Role"))).toBe("guest")
  })

  it("lists languages by name and, on change, moves every speaker to that language's voices", async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const language = screen.getByLabelText("Language")
    expect(
      within(language).getByRole("option", { name: "Brazilian Portuguese" })
    ).toBeTruthy()
    await user.selectOptions(language, "pt-BR")

    const rows = screen.getAllByRole("group", { name: /Speaker \d/ })
    const voice = within(rows[0]).getByLabelText("Voice")
    expect(value(voice)).toBe("pf_dora")
    expect(value(within(rows[1]).getByLabelText("Voice"))).toBe("pm_alex")
    expect(within(voice).queryByRole("option", { name: "Heart" })).toBeNull()
  })

  it("adds speakers with an unused voice up to six, and removes them", async () => {
    const user = userEvent.setup()
    render(
      <Harness
        initial={{
          ...brief,
          language: "en-GB",
          speakers: [{ name: "Solo", role: "narrator", voice: "bf_emma" }],
        }}
      />
    )

    expect(
      screen.queryByRole("button", { name: "Remove speaker 1" })
    ).toBeNull()
    const add = screen.getByRole("button", { name: "Add speaker" })
    expect(add.hasAttribute("disabled")).toBe(true) // en-GB has one voice: nobody else can speak

    await user.selectOptions(screen.getByLabelText("Language"), "en-US")
    await user.click(add)
    let rows = screen.getAllByRole("group", { name: /Speaker \d/ })
    expect(rows).toHaveLength(2)
    expect(value(within(rows[1]).getByLabelText("Voice"))).toBe("am_adam")
    expect(add.hasAttribute("disabled")).toBe(true) // both en-US voices are taken

    await user.click(screen.getByRole("button", { name: "Remove speaker 1" }))
    rows = screen.getAllByRole("group", { name: /Speaker \d/ })
    expect(rows).toHaveLength(1)
    expect(value(within(rows[0]).getByLabelText("Voice"))).toBe("am_adam")
  })

  it("lists languages A to Z by the name shown, not in the model's order", () => {
    render(<Harness />)

    expect(
      within(screen.getByLabelText("Language"))
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["American English", "Brazilian Portuguese", "British English"])
  })

  it("groups each speaker's voices by gender", () => {
    render(<Harness />)

    const voice = within(
      screen.getAllByRole("group", { name: /Speaker \d/ })[0]
    ).getByLabelText("Voice")
    const groups = within(voice).getAllByRole("group")
    expect(groups.map((group) => group.getAttribute("label"))).toEqual([
      "Female",
      "Male",
    ])
    expect(
      within(groups[0])
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["Heart"])
  })

  it("names the speaker inline", async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const name = within(
      screen.getAllByRole("group", { name: /Speaker \d/ })[0]
    ).getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Ada")
    expect(value(name)).toBe("Ada")
  })

  it("offers a voice under every language it speaks", async () => {
    const user = userEvent.setup()
    function Multilingual() {
      const [value, setValue] = useState<PodcastBrief>({
        ...brief,
        language: "en",
        speakers: [
          { name: "Host", role: "host", voice: "M1" },
          { name: "Guest", role: "guest", voice: "F1" },
        ],
      })
      return (
        <PodcastBriefForm
          brief={value}
          voices={multilingual}
          languages={spokenBy(multilingual)}
          voicesSource="local"
          voicedBy={null}
          onSetUpVoices={() => undefined}
          onChange={setValue}
        />
      )
    }
    render(<Multilingual />)

    await user.selectOptions(screen.getByLabelText("Language"), "fr")

    const rows = screen.getAllByRole("group", { name: /Speaker \d/ })
    expect(value(within(rows[0]).getByLabelText("Voice"))).toBe("M1")
    expect(value(within(rows[1]).getByLabelText("Voice"))).toBe("F1")
  })

  it("lists voices whose gender nobody documents in one list", () => {
    // OpenAI names its voices and nothing else about them.
    const openai: Voice[] = [
      { id: "alloy", label: "Alloy", gender: null, languages: ["en"] },
      { id: "ash", label: "Ash", gender: null, languages: ["en"] },
    ]
    render(
      <PodcastBriefForm
        brief={{
          ...brief,
          language: "en",
          speakers: [{ name: "Host", role: "host", voice: "alloy" }],
        }}
        voices={openai}
        languages={["en"]}
        voicesSource="saved"
        voicedBy={{ server: "OpenAI", model: "tts-1" }}
        onSetUpVoices={() => undefined}
        onChange={() => undefined}
      />
    )

    const voice = screen.getByLabelText("Voice")
    expect(within(voice).queryAllByRole("group")).toEqual([])
    expect(
      within(voice)
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["Alloy", "Ash"])
  })

  it("offers a server's listed voices in every language, as they state none", async () => {
    // Kokoro-FastAPI lists ids alone.
    const listed: Voice[] = [
      { id: "af_heart", label: "af_heart", gender: null, languages: [] },
      { id: "am_adam", label: "am_adam", gender: null, languages: [] },
    ]
    const user = userEvent.setup()
    function Listed() {
      const [value, setValue] = useState<PodcastBrief>({
        ...brief,
        language: "en",
        speakers: [{ name: "Host", role: "host", voice: "af_heart" }],
      })
      return (
        <PodcastBriefForm
          brief={value}
          voices={listed}
          languages={["en", "fr"]}
          voicesSource="server"
          voicedBy={{ server: "Kokoro", model: "kokoro" }}
          onSetUpVoices={() => undefined}
          onChange={setValue}
        />
      )
    }
    render(<Listed />)

    await user.selectOptions(screen.getByLabelText("Language"), "fr")

    const voice = screen.getByLabelText("Voice")
    expect(value(voice)).toBe("af_heart")
    expect(
      within(voice)
        .getAllByRole("option")
        .map((option) => option.textContent)
    ).toEqual(["af_heart", "am_adam"])
    expect(
      screen
        .getByRole("button", { name: "Add speaker" })
        .hasAttribute("disabled")
    ).toBe(false)
  })

  it("says a server voices it, and reads like the local form otherwise", () => {
    render(
      <PodcastBriefForm
        brief={{
          ...brief,
          language: "en",
          speakers: [{ name: "Host", role: "host", voice: "en_paul" }],
        }}
        voices={[
          { id: "en_paul", label: "en_paul", gender: null, languages: [] },
        ]}
        languages={["en", "fr"]}
        voicesSource="saved"
        voicedBy={{ server: "OpenRouter", model: "seed-audio-1-0" }}
        onSetUpVoices={() => undefined}
        onChange={() => undefined}
      />
    )

    expect(
      screen.getByText(
        "Voiced by seed-audio-1-0 on OpenRouter. Each line is billed by the provider."
      )
    ).toBeTruthy()
    expect(screen.getByLabelText("Language")).toBeTruthy()
    expect(screen.getByText("Speakers")).toBeTruthy()
    expect(screen.queryByText("Script language")).toBeNull()
    expect(screen.queryByText("Your voices for this model")).toBeNull()
    expect(screen.queryByText("Listed by the server")).toBeNull()
  })

  it("asks for voices before anything else when the server model has none", async () => {
    const user = userEvent.setup()
    const setUp = vi.fn()
    render(
      <PodcastBriefForm
        brief={{
          ...brief,
          language: "en",
          speakers: [{ name: "Host", role: "host", voice: "" }],
        }}
        voices={[]}
        languages={["en"]}
        voicesSource="saved"
        voicedBy={{ server: "OpenRouter", model: "seed-audio-1-0" }}
        onSetUpVoices={setUp}
        onChange={() => undefined}
      />
    )

    expect(
      screen.getByText(
        "This model needs voices before it can voice a podcast. The server doesn’t list them, so add the ones you want."
      )
    ).toBeTruthy()
    expect(screen.queryByRole("group", { name: /Speaker \d/ })).toBeNull()
    await user.click(screen.getByRole("button", { name: "Set up voices" }))
    expect(setUp).toHaveBeenCalledOnce()
  })

  it("says nothing about a server for a model on this computer", () => {
    render(<Harness />)

    expect(screen.queryByText(/Voiced by/)).toBeNull()
    expect(screen.getByLabelText("Language")).toBeTruthy()
  })
})
